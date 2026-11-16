/** public api; included by l4d2_speedwatch.sp. */

void StoreClientSample(int client, float now, bool inGrace)
{
    g_ClientSamples[client].client = client;
    g_ClientSamples[client].accountId = GetSteamAccountID(client, true);
    g_ClientSamples[client].userId = GetClientUserId(client);
    g_ClientSamples[client].engineTime = now;
    g_ClientSamples[client].excess = g_Debt[client];
    g_ClientSamples[client].consecutiveSamples = g_Strikes[client];
    g_ClientSamples[client].inGrace = inGrace;
    g_bHasSample[client] = true;
}

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
        && g_bMonitor[client] && bIsPlayingHuman(client);
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
