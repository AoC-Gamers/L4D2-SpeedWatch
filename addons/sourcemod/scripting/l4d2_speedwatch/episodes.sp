/** episodes; included by l4d2_speedwatch.sp. */

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
            g_Detections[client].persistenceTime = 0.0;
            g_Detections[client].persistenceMarker = 0;
            QueueDetectionEvent(client, SpeedWatchDetection_Active, SpeedWatchReason_None);
        }
        return;
    }
    if (commands <= 0 || float(commands) > allowed)
    {
        g_Detections[client].recoveryTime = 0.0;
        if (commands > 0 && float(commands) > allowed && g_Strikes[client] >= required)
        {
            g_Detections[client].persistenceTime += elapsed;
            if (g_Detections[client].persistenceTime >= PERSISTENCE_SECONDS)
            {
                QueueDetectionPersistence(client);
                g_Detections[client].persistenceTime = 0.0;
            }
        }
        else g_Detections[client].persistenceTime = 0.0;
        return;
    }
    g_Detections[client].persistenceTime = 0.0;
    g_Detections[client].recoveryTime += elapsed;
    if (g_Detections[client].recoveryTime >= g_cvRecoveryTime.FloatValue)
    {
        EndDetectionEpisode(client, SpeedWatchDetection_Recovered, SpeedWatchReason_NormalCadence);
    }
}

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
    g_Detections[client].persistenceTime = 0.0;
    g_Detections[client].persistenceMarker = 0;
}

void QueueDetectionEvent(int client, SpeedWatchDetectionState state, SpeedWatchDetectionReason reason)
{
    DetectionStateEvent notification;
    notification.client = client;
    notification.accountId = g_Detections[client].accountId;
    notification.userId = g_Detections[client].userId;
    notification.state = state;
    notification.reason = reason;
    notification.persistenceMarker = 0;
    notification.confirmedSeconds = 0.0;
    g_DetectionEvents.PushArray(notification, sizeof(notification));
}

void QueueDetectionPersistence(int client)
{
    DetectionStateEvent notification;
    notification.client = client;
    notification.accountId = g_Detections[client].accountId;
    notification.userId = g_Detections[client].userId;
    notification.persistenceMarker = ++g_Detections[client].persistenceMarker;
    notification.confirmedSeconds = g_Detections[client].persistenceTime;
    g_DetectionEvents.PushArray(notification, sizeof(notification));
}

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
        if (notification.persistenceMarker > 0)
        {
            DetectionLog("detections", "event=detection_persistence client=%d accountid=%d userid=%d marker=%d confirmed_seconds=%.3f",
                notification.client, notification.accountId, notification.userId, notification.persistenceMarker, notification.confirmedSeconds);
            Call_StartForward(g_hDetectionPersistenceForward);
            Call_PushCell(notification.client);
            Call_PushCell(notification.accountId);
            Call_PushCell(notification.userId);
            Call_PushCell(notification.persistenceMarker);
            Call_PushFloat(notification.confirmedSeconds);
        }
        else
        {
            DetectionLog("detections", "event=detection_state client=%d accountid=%d userid=%d state=%d reason=%d",
                notification.client, notification.accountId, notification.userId, notification.state, notification.reason);
            Call_StartForward(g_hDetectionStateForward);
            Call_PushCell(notification.client);
            Call_PushCell(notification.accountId);
            Call_PushCell(notification.userId);
            Call_PushCell(notification.state);
            Call_PushCell(notification.reason);
        }
        Call_Finish();
    }
    g_Runtime.dispatchingDetectionEvents = false;
    return true;
}
