/**
 * Detector y API de SpeedWatch. GPL-3.0-or-later.
 * Se incluye desde l4d2_speedwatch.sp; no es un plugin independiente.
 */

// Muestras de solo lectura para consumidores; cada reinicio invalida su slot.
GlobalForward g_hDetectionForward;
GlobalForward g_hDetectionStateForward;

/** Episodio por conexión; su identidad se conserva aunque el slot deje de estar disponible. */
enum struct DetectionEpisode
{
    bool active;
    int accountId;
    int userId;
    float recoveryTime;
}

/** Copia inmutable de una transición pendiente de notificar a los consumidores. */
enum struct DetectionStateEvent
{
    int client;
    int accountId;
    int userId;
    SpeedWatchDetectionState state;
    SpeedWatchDetectionReason reason;
}

DetectionEpisode g_Detections[MAXPLAYERS + 1];
ArrayList g_DetectionEvents;
SpeedWatchSample g_ClientSamples[MAXPLAYERS + 1];
bool g_bHasSample[MAXPLAYERS + 1];

// Elegibilidad y contadores por slot; se limpian al reutilizar la conexión.
bool       g_bHuman[MAXPLAYERS + 1];
bool       g_bMonitor[MAXPLAYERS + 1];
int        g_Commands[MAXPLAYERS + 1];
int        g_Strikes[MAXPLAYERS + 1];
float      g_Debt[MAXPLAYERS + 1];
float      g_GraceUntil[MAXPLAYERS + 1];
float      g_NextAlert[MAXPLAYERS + 1];
float      g_LastRate[MAXPLAYERS + 1];
float      g_LastRatio[MAXPLAYERS + 1];
// Referencias globales para comparar tiempo real y avance de la simulación.
float      g_LastEngineTime;
float      g_LastInterval;
int        g_LastTick;

/**
 * Comprueba en memoria si se permite recoger comandos o consumir una muestra.
 * No afirma que la última evaluación sea válida; eso lo indica sampleValid.
 * No consulta bibliotecas, entidades ni natives de los proveedores.
 *
 * @return             True con mapa disponible, observación abierta y sin exclusiones.
 */
bool bCanObserve()
{
    return g_Runtime.mapLoaded && !g_Runtime.observationEnded
        && !g_Runtime.modeNeedsSync
        && !g_Runtime.paused && !g_Runtime.pauseNeedsSync
        && !g_Runtime.inReady && !g_Runtime.readyUpNeedsSync;
}

/**
 * Cuenta callbacks de comandos mediante elegibilidad almacenada en memoria.
 * No modifica el comando ni utiliza cmdnum/tickcount como reloj de detección.
 * Consulta las ConVars de debug; solo con traza activa obtiene userid y formatea.
 */
public void OnPlayerRunCmdPre(int client, int buttons, int impulse, const float vel[3], const float angles[3], int weapon, int subtype, int cmdnum, int tickcount, int seed, const int mouse[2])
{
    if (!bCanObserve())
    {
        return;
    }
    // Ruta habitual: elegibilidad en memoria, incremento y traza desactivada.
    if (g_bMonitor[client])
    {
        g_Commands[client]++;
    }
    if (g_bHuman[client] && g_Log.bDebug(DEBUG_COMMANDS))
    {
        char message[192];
        Format(message, sizeof(message), "event=command slot=%d userid=%d cmdnum=%d client_tick=%d tracking=%d count=%d",
                 client, GetClientUserId(client), cmdnum, tickcount, g_bMonitor[client], g_Commands[client]);
        g_Log.Write("commands", message);
    }
}

/**
 * Evalúa la cadencia de comandos con una muestra compartida cada segundo.
 * Valida tiempo y ticks, actualiza el exceso acumulado y exige una racha antes
 * de alertar. Las muestras inválidas descartan el historial y aplican gracia.
 *
 * @param timer        Timer repetitivo que persiste entre mapas.
 * @return             Plugin_Continue para mantener la evaluación periódica.
 */
public Action OnSampleTimer(Handle timer)
{
    float now            = GetEngineTime();
    if (!g_Runtime.mapLoaded || g_Runtime.observationEnded || !bReconcileObservation(now))
    {
        g_Runtime.sampleValid = false;
        g_LastEngineTime = now;
        g_LastInterval = GetTickInterval();
        g_LastTick = GetGameTickCount();
        DebugLog(DEBUG_SAMPLES, "samples", "event=observation_sample_skipped map_loaded=%d observation_ended=%d left4dhooks_library=%d game_mode=%d mode_pending=%d pause_library=%d paused=%d pause_pending=%d readyup_library=%d in_ready=%d readyup_pending=%d",
            g_Runtime.mapLoaded, g_Runtime.observationEnded, g_Runtime.hasLeft4DHooks, g_Runtime.gameMode, g_Runtime.modeNeedsSync,
            g_Runtime.hasPause, g_Runtime.paused, g_Runtime.pauseNeedsSync,
            g_Runtime.hasReadyUp, g_Runtime.inReady, g_Runtime.readyUpNeedsSync);
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

    // Descarta muestras con simulación irregular, tickrate variable, observación
    // desactivada o escala de tiempo distinta de la normal.
    bool  processing     = IsServerProcessing();
    float timescale      = g_cvTimescale == null ? 1.0 : g_cvTimescale.FloatValue;
    g_Runtime.sampleValid = g_cvEnabled.BoolValue && processing
              && elapsed >= 0.5 && elapsed <= 2.0 && intervalStable
              && float(ticks) >= expected * 0.80 && float(ticks) <= expected * 1.20
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

    float allowed  = expected * g_cvRate.FloatValue;
    float buffer   = g_cvBurst.FloatValue / interval;
    int   required = g_cvSamples.IntValue;
    int generation = g_Runtime.observationGeneration;
    for (int client = 1; client <= MaxClients; client++)
    {
        if (!g_bHuman[client])
        {
            continue;
        }
        if (!IsClientInGame(client) || !IsPlayerAlive(client) || GetClientTeam(client) < 2)
        {
            ResetClient(client, now, SpeedWatchReason_ClientUnavailable);
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
            DebugLog(DEBUG_LIFECYCLE, "lifecycle", "event=tracking_started slot=%d userid=%d grace=%.1f", client, GetClientUserId(client), g_cvGrace.FloatValue);
            if (FlushDetectionEvents() && !bEvaluationCurrent(generation))
            {
                return Plugin_Continue;
            }
            continue;
        }

        int commands        = g_Commands[client];
        g_Commands[client]  = 0;
        g_LastRate[client]  = float(commands) / elapsed;
        g_LastRatio[client] = float(commands) / expected;
        if (now < g_GraceUntil[client])
        {
            StoreClientSample(client, now, true);
            DebugLog(DEBUG_SAMPLES, "samples", "event=client_sample slot=%d userid=%d state=grace commands=%d cmds_per_second=%.2f ratio=%.3f remaining=%.2f",
                     client, GetClientUserId(client), commands, g_LastRate[client], g_LastRatio[client], g_GraceUntil[client] - now);
            continue;
        }

        g_Debt[client] += float(commands) - allowed;
        if (g_Debt[client] < 0.0)
        {
            g_Debt[client] = 0.0;
        }
        // Limita el efecto de ráfagas antiguas; una alerta exige exceso actual.
        if (g_Debt[client] > buffer * 2.0)
        {
            g_Debt[client] = buffer * 2.0;
        }

        if (g_Debt[client] >= buffer && float(commands) > allowed)
        {
            if (g_Strikes[client] < required)
            {
                g_Strikes[client]++;
            }
        }
        else
        {
            g_Strikes[client] = 0;
        }

        StoreClientSample(client, now, false);
        DebugLog(DEBUG_SAMPLES, "samples", "event=client_sample slot=%d userid=%d state=tracking commands=%d allowed=%.2f cmds_per_second=%.2f ratio=%.3f excess=%.2f buffer=%.2f strikes=%d required=%d",
                 client, GetClientUserId(client), commands, allowed, g_LastRate[client], g_LastRatio[client], g_Debt[client], buffer, g_Strikes[client], required);
        if (g_Strikes[client] > 0)
        {
            DebugLog(DEBUG_DETECTIONS, "detections", "event=suspicion slot=%d userid=%d strikes=%d required=%d cooldown_remaining=%.2f",
                     client, GetClientUserId(client), g_Strikes[client], required, now >= g_NextAlert[client] ? 0.0 : g_NextAlert[client] - now);
        }

        int userId = g_ClientSamples[client].userId;
        UpdateDetectionEpisode(client, commands, allowed, elapsed, required);
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
            SendAlert(client);
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

/**
 * Limpia la observación de un slot y aplica el período de gracia.
 * El cooldown se conserva; solo una conexión nueva o desconexión lo elimina.
 *
 * @param client       Índice del slot que se reinicia.
 * @param now          Tiempo real del motor al iniciar la gracia.
 * @param reason       Motivo de interrupción si había un episodio activo.
 */
void ResetClient(int client, float now, SpeedWatchDetectionReason reason = SpeedWatchReason_ObservationReset)
{
    if (g_bMonitor[client] || g_Commands[client] > 0 || g_Debt[client] > 0.0)
    {
        DebugLog(DEBUG_LIFECYCLE, "lifecycle", "event=client_reset slot=%d commands=%d excess=%.2f strikes=%d", client, g_Commands[client], g_Debt[client], g_Strikes[client]);
    }
    g_bHasSample[client] = false;
    g_bMonitor[client]   = false;
    g_Commands[client]   = 0;
    g_Strikes[client]    = 0;
    g_Debt[client]       = 0.0;
    g_LastRate[client]   = 0.0;
    g_LastRatio[client]  = 0.0;
    g_GraceUntil[client] = now + g_cvGrace.FloatValue;
    EndDetectionEpisode(client, SpeedWatchDetection_Interrupted, reason);
    // Conserva el cooldown durante reinicios de ronda, retrasos y configuración.
}

/**
 * Reinicia el reloj global y el historial de todos los slots.
 *
 * @param now          Tiempo real del motor usado como nueva referencia.
 * @param reason       Motivo del reinicio para el log de lifecycle.
 * @param interruption Motivo público del cierre de los episodios activos.
 */
void ResetAll(float now, const char[] reason, SpeedWatchDetectionReason interruption = SpeedWatchReason_ObservationReset)
{
    DebugLog(DEBUG_LIFECYCLE, "lifecycle", "event=reset_all reason=%s", reason);
    g_Runtime.sampleValid = false;
    g_Runtime.observationGeneration++;
    g_LastEngineTime = now;
    g_LastInterval   = GetTickInterval();
    g_LastTick       = GetGameTickCount();
    for (int client = 1; client <= MaxClients; client++)
    {
        ResetClient(client, now, interruption);
    }
}

/** Comprueba que ningún consumidor haya invalidado la evaluación global. */
bool bEvaluationCurrent(int generation)
{
    return generation == g_Runtime.observationGeneration && bCanObserve() && g_Runtime.sampleValid;
}

/**
 * Actualiza un episodio únicamente con una muestra válida y fuera de gracia.
 * La racha de recuperación mide la cadencia actual, sin esperar a vaciar la deuda.
 * Cero comandos o cualquier exceso rompen la racha; no demuestran recuperación.
 *
 * @param client       Jugador con una muestra publicada.
 * @param commands     Comandos recibidos en esta muestra.
 * @param allowed      Límite de comandos para el intervalo medido.
 * @param elapsed      Duración válida de la muestra, en segundos.
 * @param required     Racha necesaria para iniciar un episodio.
 */
void UpdateDetectionEpisode(int client, int commands, float allowed, float elapsed, int required)
{
    if (!g_Detections[client].active)
    {
        if (g_Strikes[client] >= required)
        {
            g_Detections[client].active = true;
            g_Detections[client].accountId = g_ClientSamples[client].accountId;
            g_Detections[client].userId = g_ClientSamples[client].userId;
            g_Detections[client].recoveryTime = 0.0;
            QueueDetectionEvent(client, SpeedWatchDetection_Active, SpeedWatchReason_None);
        }
        return;
    }
    if (commands <= 0 || float(commands) > allowed)
    {
        g_Detections[client].recoveryTime = 0.0;
        return;
    }
    g_Detections[client].recoveryTime += elapsed;
    if (g_Detections[client].recoveryTime >= g_cvRecoveryTime.FloatValue)
    {
        EndDetectionEpisode(client, SpeedWatchDetection_Recovered, SpeedWatchReason_NormalCadence);
    }
}

/**
 * Encola un terminal antes de borrar la identidad original del episodio.
 * Los reinicios no notifican dentro de sus bucles de modificación de estado.
 */
void EndDetectionEpisode(int client, SpeedWatchDetectionState state, SpeedWatchDetectionReason reason)
{
    if (!g_Detections[client].active)
    {
        return;
    }
    QueueDetectionEvent(client, state, reason);
    g_Detections[client].active = false;
    g_Detections[client].accountId = 0;
    g_Detections[client].userId = 0;
    g_Detections[client].recoveryTime = 0.0;
}

/** Copia la identidad del episodio; no consulta un slot que pudo reutilizarse. */
void QueueDetectionEvent(int client, SpeedWatchDetectionState state, SpeedWatchDetectionReason reason)
{
    DetectionStateEvent notification;
    notification.client = client;
    notification.accountId = g_Detections[client].accountId;
    notification.userId = g_Detections[client].userId;
    notification.state = state;
    notification.reason = reason;
    g_DetectionEvents.PushArray(notification, sizeof(notification));
}

/**
 * Entrega cambios en orden después de completar las modificaciones internas.
 * Un cambio provocado dentro del forward espera a que todos los consumidores
 * reciban el cambio actual. Cada transición se registra incluso sin debug.
 *
 * @return             True si se entregaron notificaciones a consumidores.
 */
bool FlushDetectionEvents()
{
    if (g_Runtime.dispatchingDetectionEvents || g_DetectionEvents.Length == 0)
    {
        return false;
    }
    g_Runtime.dispatchingDetectionEvents = true;
    while (g_DetectionEvents.Length > 0)
    {
        DetectionStateEvent notification;
        g_DetectionEvents.GetArray(0, notification, sizeof(notification));
        g_DetectionEvents.Erase(0);
        DetectionLog("detections", "event=detection_state client=%d accountid=%d userid=%d state=%d reason=%d",
            notification.client, notification.accountId, notification.userId, notification.state, notification.reason);
        Call_StartForward(g_hDetectionStateForward);
        Call_PushCell(notification.client);
        Call_PushCell(notification.accountId);
        Call_PushCell(notification.userId);
        Call_PushCell(notification.state);
        Call_PushCell(notification.reason);
        Call_Finish();
    }
    g_Runtime.dispatchingDetectionEvents = false;
    return true;
}

/**
 * Registra siempre la detección y envía la alerta a su audiencia configurada.
 * El llamador ya debe haber validado el umbral y el cooldown del sospechoso.
 *
 * @param suspect      Índice del jugador humano que originó la alerta.
 */
void SendAlert(int suspect)
{
    // Captura valores antes de notificar a consumidores que pueden cambiar el estado.
    SpeedWatchSample sample;
    sample = g_ClientSamples[suspect];
    int userid = sample.userId;
    DetectionLog("detections", "event=alert client=%d accountid=%d suspect_userid=%d cmds_per_second=%.2f ratio=%.3f excess=%.2f strikes=%d public=%d",
              sample.client, sample.accountId, userid, sample.commandsPerSecond, sample.ratio, sample.excess,
              sample.consecutiveSamples, g_cvPublic.BoolValue);
    for (int target = 1; target <= MaxClients; target++)
    {
        if (!IsClientInGame(target) || IsFakeClient(target))
        {
            continue;
        }
        if (g_cvPublic.BoolValue || CheckCommandAccess(target, "sm_speedwatch_alerts", ADMFLAG_GENERIC, true))
        {
            PrintToChat(target, "[SpeedWatch] %T", "SpeedSuspicion", target,
                        suspect, userid, g_LastRate[suspect], g_LastRatio[suspect]);
        }
    }
    PrintToServer("[SpeedWatch] suspect_userid=%d cmds_per_second=%.1f ratio=%.2f excess=%.1f samples=%d",
                  userid, sample.commandsPerSecond, sample.ratio, sample.excess, sample.consecutiveSamples);

    // Notificación posterior al log/chat; el resultado del forward no cancela la alerta.
    Call_StartForward(g_hDetectionForward);
    Call_PushCell(sample.client);
    Call_PushCell(sample.accountId);
    Call_PushCell(sample.userId);
    Call_PushFloat(sample.commandsPerSecond);
    Call_PushFloat(sample.ratio);
    Call_PushFloat(sample.excess);
    Call_PushCell(sample.consecutiveSamples);
    Call_Finish();
}

/**
 * Publica una copia de la última evaluación sin añadir trabajo por comando.
 * La identidad corresponde a la conexión y al momento de esta muestra.
 *
 * @param client       Índice del jugador evaluado.
 * @param now          Tiempo real del motor al evaluar.
 * @param inGrace      True si la muestra aún no puede acumular sospechas.
 */
void StoreClientSample(int client, float now, bool inGrace)
{
    g_ClientSamples[client].client = client;
    g_ClientSamples[client].accountId = GetSteamAccountID(client, true);
    g_ClientSamples[client].userId = GetClientUserId(client);
    g_ClientSamples[client].engineTime = now;
    g_ClientSamples[client].commandsPerSecond = g_LastRate[client];
    g_ClientSamples[client].ratio = g_LastRatio[client];
    g_ClientSamples[client].excess = g_Debt[client];
    g_ClientSamples[client].consecutiveSamples = g_Strikes[client];
    g_ClientSamples[client].inGrace = inGrace;
    g_bHasSample[client] = true;
}

/**
 * Copia una muestra válida al consumidor; sin muestra, devuelve el struct a cero.
 * Rechaza slots fuera de rango con error de native y no expone conexiones viejas.
 *
 * @return             True si se copió la última muestra del jugador solicitado.
 */
public any Native_GetClientSample(Handle plugin, int numParams)
{
    int client = GetNativeCell(1);
    if (client < 1 || client > MaxClients)
    {
        return ThrowNativeError(SP_ERROR_NATIVE, "Invalid client index %d", client);
    }

    SpeedWatchSample sample;
    bool valid = bCanObserve() && g_Runtime.sampleValid
        && g_bHasSample[client]
        && g_bHuman[client] && g_bMonitor[client] && IsClientInGame(client)
        && IsPlayerAlive(client) && GetClientTeam(client) >= 2;
    if (valid)
    {
        float age = GetEngineTime() - g_ClientSamples[client].engineTime;
        valid = g_ClientSamples[client].userId == GetClientUserId(client)
            && age >= 0.0 && age <= 2.0;
    }
    if (valid)
    {
        sample = g_ClientSamples[client];
    }
    SetNativeArray(2, sample, sizeof(sample));
    return valid;
}
