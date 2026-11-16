/** policy; included by l4d2_speedwatch.sp. */

void EvaluateNativeCadence(int client, int commands, float allowed, float buffer, int required)
{
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
}
