/** notifications; included by l4d2_speedwatch.sp. */

void SendAlert(int suspect)
{
    // Captura valores antes de notificar a consumidores que pueden cambiar el estado.
    SpeedWatchSample sample;
    sample = g_ClientSamples[suspect];
    int userid = sample.userId;
    DetectionClientLog(suspect, "detections", "event=alert client=%d accountid=%d suspect_userid=%d cmds_per_second=%.2f ratio=%.3f excess=%.2f strikes=%d public=%d",
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
                        suspect, userid, sample.commandsPerSecond, sample.ratio);
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
