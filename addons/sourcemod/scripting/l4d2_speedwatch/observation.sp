/** observation; included by l4d2_speedwatch.sp. */

bool bCanObserve()
{
    return bNativeDetectorReady() && g_Runtime.mapLoaded && !g_Runtime.observationEnded
        && !g_Runtime.modeNeedsSync
        && !g_Runtime.paused && !g_Runtime.pauseNeedsSync
        && !g_Runtime.inReady && !g_Runtime.readyUpNeedsSync;
}

bool bIsPlayingHuman(int client)
{
    if (client < 1 || client > MaxClients || !g_bHuman[client]
        || !IsClientInGame(client) || !IsPlayerAlive(client))
    {
        return false;
    }
    int team = GetClientTeam(client);
    return team == 2 || team == 3;
}

bool bHasClientObservation(int client)
{
    return g_bMonitor[client] || g_bHasSample[client] || g_Detections[client].active
        || g_Strikes[client] != 0 || g_Debt[client] > 0.0;
}

public Action OnSampleTimer(Handle timer)
{
    g_Log.evaluation++;
    float now            = GetEngineTime();
    ReconcileNativeCore();
    if (!g_Runtime.mapLoaded || g_Runtime.observationEnded || !bReconcileObservation(now))
    {
        PulseNativeCore(false);
        g_Runtime.sampleValid = false;
        g_LastEngineTime = now;
        g_LastInterval = GetTickInterval();
        g_LastTick = GetGameTickCount();
        DebugLog(DEBUG_SAMPLES, "samples", "event=observation_sample_skipped map_loaded=%d observation_ended=%d left4dhooks_library=%d game_mode=%d mode_pending=%d pause_library=%d paused=%d pause_pending=%d readyup_library=%d in_ready=%d readyup_pending=%d core_available=%d core_ready=%d core_pending=%d caps=%d",
            g_Runtime.mapLoaded, g_Runtime.observationEnded, g_Runtime.hasLeft4DHooks, g_Runtime.gameMode, g_Runtime.modeNeedsSync,
            g_Runtime.hasPause, g_Runtime.paused, g_Runtime.pauseNeedsSync,
            g_Runtime.hasReadyUp, g_Runtime.inReady, g_Runtime.readyUpNeedsSync,
            g_Runtime.coreAvailable, bNativeDetectorReady(), g_Runtime.coreNeedsSync, g_Runtime.coreCapabilities);
        g_Log.Flush();
        FlushDetectionEvents();
        return Plugin_Continue;
    }
    float elapsed        = now - g_LastEngineTime;
    float interval       = GetTickInterval();
    int   tick           = GetGameTickCount();
    int   ticks          = tick - g_LastTick;
    float expected       = elapsed / interval;
    bool  intervalStable = FloatAbs(interval - g_LastInterval) < 0.000001;
    g_LastEngineTime     = now;
    g_LastInterval       = interval;
    g_LastTick           = tick;

    // El core valida duración, intervalo y ticks de su propia ventana. Aquí solo
    // se aplican activación, procesamiento y escala de tiempo de la partida.
    bool  processing     = IsServerProcessing();
    float timescale      = g_cvTimescale == null ? 1.0 : g_cvTimescale.FloatValue;
    g_Runtime.sampleValid = bNativeDetectorReady() && g_cvEnabled.BoolValue && processing
              && FloatAbs(timescale - 1.0) < 0.001;
    DebugLog(DEBUG_SAMPLES, "samples", "event=server_sample valid=%d map_loaded=%d observation_ended=%d enabled=%d processing=%d elapsed=%.3f ticks=%d expected=%.2f interval=%.6f stable=%d timescale=%.3f",
             g_Runtime.sampleValid, g_Runtime.mapLoaded, g_Runtime.observationEnded, g_cvEnabled.BoolValue, processing, elapsed, ticks, expected, interval, intervalStable, timescale);
    if (!g_Runtime.sampleValid)
    {
        ResetAll(now, "invalid_sample", SpeedWatchReason_InvalidSample);
        g_Log.Flush();
        FlushDetectionEvents();
        return Plugin_Continue;
    }

    PulseNativeCore(true);
    int   required = g_cvSamples.IntValue;
    int generation = g_Runtime.observationGeneration;
    MovementProfile profile;
    for (int client = 1; client <= MaxClients; client++)
    {
        if (!g_bHuman[client])
        {
            continue;
        }
        if (!bIsPlayingHuman(client))
        {
            // Espectadores y muertos sin observación no necesitan un reset cada segundo.
            // Al volver a ser elegibles, la rama !g_bMonitor aplica gracia nueva.
            if (bHasClientObservation(client))
            {
                ResetClient(client, now, SpeedWatchReason_ClientUnavailable);
            }
            if (FlushDetectionEvents() && !bEvaluationCurrent(generation))
            {
                return Plugin_Continue;
            }
            continue;
        }
        if (!g_bMonitor[client])
        {
            ResetClient(client, now);
            g_bMonitor[client] = true;
            SetNativeParticipant(client, true);
            DebugLog(DEBUG_LIFECYCLE, "lifecycle", "event=tracking_started slot=%d userid=%d grace=%.1f", client, GetClientUserId(client), g_cvGrace.FloatValue);
            if (FlushDetectionEvents() && !bEvaluationCurrent(generation))
            {
                return Plugin_Continue;
            }
            continue;
        }

        // The core is the only command source. Never substitute reception counts
        // or a SourcePawn callback when a native window is missing/degraded.
        SetNativeParticipant(client, true);
        NativeCadenceWindow window;
        if (!EvaluateNativeWindow(client, window))
        {
            ClearClientDetection(client, now, SpeedWatchReason_InvalidSample);
            if (FlushDetectionEvents() && !bEvaluationCurrent(generation))
            {
                return Plugin_Continue;
            }
            continue;
        }
        int commands = window.commands;
        float duration = window.duration;
        float nativeInterval = window.interval;
        float nativeExpected = duration / nativeInterval;
        float allowed = nativeExpected * g_cvRate.FloatValue;
        float buffer = g_cvBurst.FloatValue / nativeInterval;
        g_ClientSamples[client].commandsPerSecond = float(commands) / duration;
        g_ClientSamples[client].ratio = float(commands) / nativeExpected;
        MovementContext context;
        if (now < g_GraceUntil[client])
        {
            StoreClientSample(client, now, true);
            CaptureSampleContext(client, now, false, profile, context);
            DebugClientLog(DEBUG_SAMPLES, "samples", client, "event=client_sample slot=%d userid=%d state=grace commands=%d cmds_per_second=%.2f ratio=%.3f remaining=%.2f",
                     client, GetClientUserId(client), commands, g_ClientSamples[client].commandsPerSecond, g_ClientSamples[client].ratio, g_GraceUntil[client] - now);
            continue;
        }

        EvaluateNativeCadence(client, commands, allowed, buffer, required);

        StoreClientSample(client, now, false);
        DebugClientLog(DEBUG_SAMPLES, "samples", client, "event=client_sample slot=%d userid=%d state=tracking commands=%d allowed=%.2f cmds_per_second=%.2f ratio=%.3f excess=%.2f buffer=%.2f strikes=%d required=%d",
                 client, GetClientUserId(client), commands, allowed, g_ClientSamples[client].commandsPerSecond, g_ClientSamples[client].ratio, g_Debt[client], buffer, g_Strikes[client], required);
        if (g_Strikes[client] > 0)
        {
            DebugClientLog(DEBUG_DETECTIONS, "detections", client, "event=suspicion slot=%d userid=%d strikes=%d required=%d cooldown_remaining=%.2f",
                     client, GetClientUserId(client), g_Strikes[client], required, now >= g_NextAlert[client] ? 0.0 : g_NextAlert[client] - now);
        }

        CaptureSampleContext(client, now, g_Strikes[client] >= required && now >= g_NextAlert[client], profile, context);
        int userId = g_ClientSamples[client].userId;
        UpdateDetectionEpisode(client, commands, allowed, duration, required);
        if (FlushDetectionEvents())
        {
            if (!bEvaluationCurrent(generation))
            {
                g_Log.Flush();
                return Plugin_Continue;
            }
            // Solo se revalida tras notificar a consumidores externos.
            if (!g_bHasSample[client] || !IsClientInGame(client) || GetClientUserId(client) != userId)
            {
                continue;
            }
        }

        if (g_Strikes[client] >= required && now >= g_NextAlert[client])
        {
            g_NextAlert[client] = now + g_cvCooldown.FloatValue;
            SendAlert(client, context, profile);
            // Un consumidor puede pausar, iniciar readyup o cambiar reglas en el forward.
            if (!bEvaluationCurrent(generation))
            {
                g_Log.Flush();
                return Plugin_Continue;
            }
        }
    }
    g_Log.Flush();
    return Plugin_Continue;
}

void ResetClient(int client, float now, SpeedWatchDetectionReason reason = SpeedWatchReason_ObservationReset)
{
    SetNativeParticipant(client, false);
    g_bMonitor[client] = false;
    ClearClientDetection(client, now, reason);
}

void ClearClientDetection(int client, float now, SpeedWatchDetectionReason reason)
{
    g_bHasSample[client] = false;
    g_Strikes[client]    = 0;
    g_Debt[client]       = 0.0;
    g_ClientSamples[client].commandsPerSecond   = 0.0;
    g_ClientSamples[client].ratio  = 0.0;
    g_GraceUntil[client] = now + g_cvGrace.FloatValue;
    EndDetectionEpisode(client, SpeedWatchDetection_Interrupted, reason);
    // Conserva el cooldown durante reinicios de ronda, retrasos y configuración.
}

void ResetAll(float now, const char[] reason, SpeedWatchDetectionReason interruption = SpeedWatchReason_ObservationReset)
{
    DebugLog(DEBUG_LIFECYCLE, "lifecycle", "event=reset_all reason=%s", reason);
    g_Runtime.sampleValid = false;
    g_Runtime.observationGeneration++;
    PulseNativeCore(false);
    g_LastEngineTime = now;
    g_LastInterval   = GetTickInterval();
    g_LastTick       = GetGameTickCount();
    for (int client = 1; client <= MaxClients; client++)
    {
        ResetClient(client, now, interruption);
    }
}

bool bEvaluationCurrent(int generation)
{
    return generation == g_Runtime.observationGeneration && bCanObserve() && g_Runtime.sampleValid;
}
