/** Read-only API diagnostic; never owns observation and never enters runtime packages. */
#pragma semicolon 1
#pragma newdecls required
#include <sourcemod>
#undef REQUIRE_EXTENSIONS
#include <l4d2_speedwatch_core>
public Plugin myinfo = { name = "SpeedWatch Core API Test", author = "Lechuga", description = "Read native telemetry repeatedly", version = "0.9.0", url = "https://github.com/AoC-Gamers/L4D2-SpeedWatch" };
public void OnPluginStart()
{
    RegAdminCmd("sm_speedwatch_core_api_test", OnCoreTest, ADMFLAG_ROOT);
}
public Action OnCoreTest(int client, int args)
{
    if (GetFeatureStatus(FeatureType_Native, "SpeedWatchCore_GetApiVersion") != FeatureStatus_Available)
    {
        ReplyToCommand(client, "[Core API Test] unavailable; legacy detector remains usable");
        return Plugin_Handled;
    }
    if (SpeedWatchCore_GetApiVersion() != SPEEDWATCH_CORE_API_VERSION)
    {
        ReplyToCommand(client, "[Core API Test] incompatible API");
        return Plugin_Handled;
    }
    for (int target = 1; target <= MaxClients; target++)
    {
        int first[SPEEDWATCH_CORE_SAMPLE_CELLS + 2];
        int second[SPEEDWATCH_CORE_SAMPLE_CELLS];
        first[SPEEDWATCH_CORE_SAMPLE_CELLS] = 12345;
        bool exists = SpeedWatchCore_GetSample(target, first, sizeof(first));
        bool repeated = SpeedWatchCore_GetSample(target, second, sizeof(second));
        if (exists != repeated || first[SPEEDWATCH_CORE_SAMPLE_CELLS] != 12345)
        {
            LogError("[Core API Test] output/availability violation slot=%d", target);
        }
        for (int i = 0; i < sizeof(second); i++)
        {
            if (first[i] != second[i])
            {
                LogError("[Core API Test] destructive read slot=%d cell=%d", target, i);
            }
        }
        if (exists)
        {
            ReplyToCommand(client, "slot=%d userid=%d sample=%d:%d caps=%d quality=%d attempts=%d:%d",
                target, first[5], first[11], first[10], first[3], first[4], first[34], first[33]);
        }
    }
    return Plugin_Handled;
}
