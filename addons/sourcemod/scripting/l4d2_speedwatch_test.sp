/**
 * Consumidor de diagnóstico de la API pública de SpeedWatch. GPL-3.0-or-later.
 * No forma parte del despliegue ordinario ni genera detecciones artificiales.
 */
#pragma semicolon 1
#pragma newdecls required

#include <sourcemod>
#if !defined SPEEDWATCH_TEST_REQUIRED
    #undef REQUIRE_PLUGIN
#endif
#include <l4d2_speedwatch>

public Plugin myinfo =
{
    name = "L4D2 SpeedWatch API Test",
    author = "Lechuga",
    description = "Checks public sample output and receives detection forwards",
    version = "0.8.0",
    url = "https://github.com/AoC-Gamers/L4D2-SpeedWatch"
};

/** Secuencia observada; un consumidor tardío puede recibir solo el terminal. */
enum struct ObservedEpisode
{
    int userId;
    int accountId;
    bool active;
}
ObservedEpisode g_Observed[MAXPLAYERS + 1];

/** Descarta únicamente la secuencia local cuando cambia el proveedor. */
public void OnLibraryAdded(const char[] name)
{
    ResetObservedProvider(name);
}

/** Una recarga del proveedor comienza un flujo de episodios nuevo. */
public void OnLibraryRemoved(const char[] name)
{
    ResetObservedProvider(name);
}

/** Los callbacks de biblioteca solo modifican memoria del consumidor. */
void ResetObservedProvider(const char[] name)
{
    if (StrEqual(name, "l4d2_speedwatch"))
    {
        for (int client = 1; client <= MaxClients; client++)
        {
            g_Observed[client].userId = 0;
            g_Observed[client].accountId = 0;
            g_Observed[client].active = false;
        }
    }
}

/** Registra un diagnóstico manual para poder probar carga/descarga del proveedor. */
public void OnPluginStart()
{
    RegAdminCmd("sm_speedwatch_api_test", OnAPITestCommand, ADMFLAG_ROOT,
        "Check SpeedWatch API availability and current samples");
}

/** Comprueba el contrato de salida utilizando únicamente los natives públicos. */
public Action OnAPITestCommand(int client, int args)
{
    if (!LibraryExists("l4d2_speedwatch"))
    {
        ReplyToCommand(client, "[SpeedWatch API Test] Provider unavailable; no native called.");
        return Plugin_Handled;
    }
    int available;
    int errors;
    for (int target = 1; target <= MaxClients; target++)
    {
        SpeedWatchSample sample;
        // Valores no nulos permiten comprobar que false limpia todo el struct.
        sample.client = -1;
        sample.accountId = -1;
        sample.userId = -1;
        sample.engineTime = -1.0;
        sample.commandsPerSecond = -1.0;
        sample.ratio = -1.0;
        sample.excess = -1.0;
        sample.consecutiveSamples = -1;
        sample.inGrace = true;
        if (!SpeedWatch_GetClientSample(target, sample))
        {
            if (sample.client != 0 || sample.accountId != 0 || sample.userId != 0
                || sample.engineTime != 0.0 || sample.commandsPerSecond != 0.0
                || sample.ratio != 0.0 || sample.excess != 0.0
                || sample.consecutiveSamples != 0 || sample.inGrace)
            {
                errors++;
                LogError("[SpeedWatch API Test] False result did not clear slot %d", target);
            }
            continue;
        }
        available++;
        if (sample.client != target || GetClientOfUserId(sample.userId) != target
            || !IsClientInGame(target) || IsFakeClient(target)
            || sample.commandsPerSecond < 0.0 || sample.ratio < 0.0 || sample.excess < 0.0)
        {
            errors++;
            LogError("[SpeedWatch API Test] Invalid sample contract for slot %d", target);
        }
        ReplyToCommand(client, "slot=%d accountid=%d userid=%d time=%.3f cmds/s=%.2f ratio=%.3f excess=%.2f strikes=%d grace=%d",
            sample.client, sample.accountId, sample.userId, sample.engineTime,
            sample.commandsPerSecond, sample.ratio, sample.excess, sample.consecutiveSamples, sample.inGrace);
    }
    ReplyToCommand(client, "[SpeedWatch API Test] available=%d errors=%d", available, errors);
    return Plugin_Handled;
}

/** Recibe la identidad y las métricas capturadas sin sancionar al jugador. */
public void SpeedWatch_OnDetection(int client, int accountId, int userId,
    float commandsPerSecond, float ratio, float excess, int consecutiveSamples)
{
    bool sameConnection = client >= 1 && client <= MaxClients
        && GetClientOfUserId(userId) == client && IsClientInGame(client);
    PrintToServer("[SpeedWatch API Test] detection client=%d accountid=%d userid=%d same_connection=%d cmds/s=%.2f ratio=%.3f excess=%.2f strikes=%d",
        client, accountId, userId, sameConnection, commandsPerSecond, ratio, excess, consecutiveSamples);
}

/** Valida orden e identidad sin generar detecciones ni acciones sobre jugadores. */
public void SpeedWatch_OnDetectionStateChanged(int client, int accountId, int userId,
    SpeedWatchDetectionState state, SpeedWatchDetectionReason reason)
{
    if (client < 1 || client > MaxClients || userId <= 0
        || state < SpeedWatchDetection_Active || state > SpeedWatchDetection_Interrupted
        || (state == SpeedWatchDetection_Active && reason != SpeedWatchReason_None)
        || (state == SpeedWatchDetection_Recovered && reason != SpeedWatchReason_NormalCadence)
        || (state == SpeedWatchDetection_Interrupted
            && (reason <= SpeedWatchReason_NormalCadence || reason > SpeedWatchReason_ObservationReset)))
    {
        LogError("[SpeedWatch API Test] Invalid state contract client=%d userid=%d state=%d reason=%d",
            client, userId, state, reason);
        return;
    }
    bool observedStart = g_Observed[client].active;
    if (state == SpeedWatchDetection_Active)
    {
        if (observedStart)
        {
            LogError("[SpeedWatch API Test] Active without terminal slot=%d old_userid=%d userid=%d",
                client, g_Observed[client].userId, userId);
        }
        g_Observed[client].userId = userId;
        g_Observed[client].accountId = accountId;
        g_Observed[client].active = true;
    }
    else
    {
        if (observedStart && (g_Observed[client].userId != userId || g_Observed[client].accountId != accountId))
        {
            LogError("[SpeedWatch API Test] Terminal identity changed slot=%d userid=%d accountid=%d",
                client, userId, accountId);
        }
        if (!observedStart && g_Observed[client].userId == userId)
        {
            LogError("[SpeedWatch API Test] Duplicate terminal slot=%d userid=%d", client, userId);
        }
        g_Observed[client].active = false;
        g_Observed[client].userId = userId;
        g_Observed[client].accountId = accountId;
    }
    PrintToServer("[SpeedWatch API Test] state client=%d accountid=%d userid=%d state=%d reason=%d observed_start=%d same_connection=%d",
        client, accountId, userId, state, reason, observedStart, GetClientOfUserId(userId) == client);
}
