/** Optional native telemetry. The legacy callback remains the detection source. */
ConVar g_cvCoreCompare;
int g_CoreSampleId[MAXPLAYERS + 1];
int g_CoreSampleIdHigh[MAXPLAYERS + 1];
bool g_CoreHasSample[MAXPLAYERS + 1];
float g_CoreSampleReceivedAt[MAXPLAYERS + 1];
int g_CoreSamples[MAXPLAYERS + 1][SPEEDWATCH_CORE_SAMPLE_CELLS];

void ReconcileNativeCore()
{
    if (!g_Runtime.coreNeedsSync)
    {
        return;
    }
    bool previouslyAvailable = g_Runtime.coreAvailable;
    g_Runtime.coreNeedsSync = false;
    g_Runtime.coreAvailable = GetFeatureStatus(FeatureType_Native, "SpeedWatchCore_GetApiVersion") == FeatureStatus_Available
        && GetFeatureStatus(FeatureType_Native, "SpeedWatchCore_GetCapabilities") == FeatureStatus_Available
        && GetFeatureStatus(FeatureType_Native, "SpeedWatchCore_Pulse") == FeatureStatus_Available
        && GetFeatureStatus(FeatureType_Native, "SpeedWatchCore_SetParticipant") == FeatureStatus_Available
        && GetFeatureStatus(FeatureType_Native, "SpeedWatchCore_GetSample") == FeatureStatus_Available
        && GetFeatureStatus(FeatureType_Native, "SpeedWatchCore_GetStatus") == FeatureStatus_Available;
    g_Runtime.coreCapabilities = 0;
    if (g_Runtime.coreAvailable)
    {
        g_Runtime.coreAvailable = SpeedWatchCore_GetApiVersion() == SPEEDWATCH_CORE_API_VERSION;
        if (g_Runtime.coreAvailable)
        {
            g_Runtime.coreCapabilities = SpeedWatchCore_GetCapabilities();
        }
    }
    // A changed diagnostic source invalidates both histories conservatively.
    ResetAll(GetEngineTime(), "native_core_sync", SpeedWatchReason_DependencyChanged);
    DebugLog(DEBUG_GENERAL, "general", "event=native_core_sync available=%d previous=%d capabilities=%d detection_backend=legacy",
        g_Runtime.coreAvailable, previouslyAvailable, g_Runtime.coreCapabilities);
}

void PulseNativeCore(bool enabled)
{
    if (g_Runtime.coreAvailable)
    {
        SpeedWatchCore_Pulse(enabled && g_cvCoreCompare.BoolValue, g_Runtime.observationGeneration);
    }
}

void SetNativeParticipant(int client, bool enabled)
{
    if (!enabled)
    {
        g_CoreHasSample[client] = false;
        g_CoreSampleId[client] = 0;
        g_CoreSampleIdHigh[client] = 0;
    }
    if (g_Runtime.coreAvailable)
    {
        SpeedWatchCore_SetParticipant(client, enabled && g_cvCoreCompare.BoolValue);
    }
}

void ReadNativeSample(int client)
{
    g_CoreHasSample[client] = false;
    if (!g_Runtime.coreAvailable || !g_cvCoreCompare.BoolValue)
    {
        return;
    }
    int sample[SPEEDWATCH_CORE_SAMPLE_CELLS];
    if (!SpeedWatchCore_GetSample(client, sample, sizeof(sample))
        || sample[5] != GetClientUserId(client) || sample[6] != GetClientSerial(client))
    {
        return;
    }
    g_CoreHasSample[client] = true;
    for (int i = 0; i < sizeof(sample); i++)
    {
        g_CoreSamples[client][i] = sample[i];
    }
    if (sample[10] != g_CoreSampleId[client] || sample[11] != g_CoreSampleIdHigh[client])
    {
        g_CoreSampleReceivedAt[client] = GetEngineTime();
        g_CoreSampleId[client] = sample[10];
        g_CoreSampleIdHigh[client] = sample[11];
        DebugLog(DEBUG_SAMPLES, "samples", "event=native_comparison slot=%d userid=%d sample_lo=%d sample_hi=%d caps=%d quality=%d duration=%.3f blocks_lo=%d attempts_lo=%d legacy_cmds_per_second=%.2f",
            client, sample[5], sample[10], sample[11], sample[3], sample[4], view_as<float>(sample[19]), sample[21], sample[33], g_LastRate[client]);
    }
}

void ShowNativeCoreStatus(int client)
{
    ReplyToCommand(client, "[SpeedWatch] detection_backend=legacy native_compare=%d native_available=%d caps=%d pending=%d",
        g_cvCoreCompare.BoolValue, g_Runtime.coreAvailable, g_Runtime.coreCapabilities, g_Runtime.coreNeedsSync);
    if (g_Runtime.coreAvailable)
    {
        ReplyToCommand(client, "[SpeedWatch] native_participants=%d native_reserved_bytes=%d native_max_bytes=%d degradation=experimental_no_executed_or_physical_signal",
            SpeedWatchCore_GetStatus(0), SpeedWatchCore_GetStatus(1), SpeedWatchCore_GetStatus(2));
        for (int target = 1; target <= MaxClients; target++)
        {
            if (g_bMonitor[target] && IsClientInGame(target))
            {
                ReadNativeSample(target);
            }
            if (g_CoreHasSample[target] && g_bHasSample[target])
            {
                ReplyToCommand(client, "[SpeedWatch] native slot=%d sample=%d:%d quality=%d caps=%d age_since_receipt=%.3f blocks=%d:%d attempts=%d:%d duration=%.3f",
                    target, g_CoreSamples[target][11], g_CoreSamples[target][10], g_CoreSamples[target][4], g_CoreSamples[target][3], GetEngineTime() - g_CoreSampleReceivedAt[target],
                    g_CoreSamples[target][22], g_CoreSamples[target][21], g_CoreSamples[target][34], g_CoreSamples[target][33],
                    view_as<float>(g_CoreSamples[target][19]));
            }
        }
    }
}
