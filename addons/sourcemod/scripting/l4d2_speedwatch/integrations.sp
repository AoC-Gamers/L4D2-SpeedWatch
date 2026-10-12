/**
 * Integraciones opcionales de SpeedWatch. GPL-3.0-or-later.
 * Se incluye desde l4d2_speedwatch.sp; no es un plugin independiente.
 */

/**
 * Cierra la mitad Versus después del cálculo de score y del cierre efectivo.
 * El proveedor no emite este forward si otro plugin bloqueó el cierre.
 */
public void L4D2_OnEndVersusModeRound_Post()
{
    CloseObservation(GetEngineTime(), "versus_mode_round_end");
}

/**
 * Acepta el modo base comunicado por Left4DHooks e invalida las muestras.
 * El forward ya proporciona el valor; no repite la consulta al native.
 *
 * @param gamemode     Modo base comunicado por el proveedor.
 */
public void L4D_OnGameModeChange(int gamemode)
{
    g_Runtime.gameMode = gamemode;
    g_Runtime.modeNeedsSync = false;
    ResetAll(GetEngineTime(), "game_mode_change", SpeedWatchReason_GameModeChanged);
    DebugLog(DEBUG_LIFECYCLE, "lifecycle", "event=game_mode_forward game_mode=%d", gamemode);
    g_Log.Flush();
    FlushDetectionEvents();
}

/**
 * Recibe el forward del proveedor pause y suspende el conteo inmediatamente.
 */
public void OnPause()
{
    HandlePauseForward(true, "pause_start");
}

/**
 * Recibe el forward de reanudación y solicita confirmar el estado de pausa.
 */
public void OnUnpause()
{
    HandlePauseForward(false, "pause_end");
}

/**
 * Aplica una transición de pausa, borra muestras y conserva el cooldown.
 *
 * @param paused       Estado comunicado por el forward del proveedor.
 * @param reason       Motivo que se incluirá en el diagnóstico del reinicio.
 */
void HandlePauseForward(bool paused, const char[] reason)
{
    g_Runtime.paused = paused;
    g_Runtime.pauseNeedsSync = true;
    ResetAll(GetEngineTime(), reason, SpeedWatchReason_Pause);
    DebugLog(DEBUG_LIFECYCLE, "lifecycle", "event=pause_forward paused=%d reason=%s", paused, reason);
    g_Log.Flush();
    FlushDetectionEvents();
}

/**
 * Consulta pause si su biblioteca está presente y garantiza IsInPause.
 * Descarta la muestra de transición y aplica gracia al sincronizar el estado.
 * Sin proveedor, permite continuar con las comprobaciones generales del detector.
 *
 * @param now          Tiempo real del motor utilizado para reiniciar el historial.
 * @return             True si el estado está sincronizado y no existe pausa.
 */
bool bReconcilePause(float now)
{
    bool paused = false;
    if (g_Runtime.hasPause)
    {
        paused = IsInPause();
    }
    if (g_Runtime.pauseNeedsSync || paused != g_Runtime.paused)
    {
        g_Runtime.paused = paused;
        g_Runtime.pauseNeedsSync = false;
        ResetAll(now, paused ? "pause_sync_active" : "pause_sync_resume",
            paused ? SpeedWatchReason_Pause : SpeedWatchReason_DependencyChanged);
        DebugLog(DEBUG_LIFECYCLE, "lifecycle", "event=pause_sync library=%d paused=%d late_load=%d",
            g_Runtime.hasPause, paused, g_Runtime.lateLoad);
        return false;
    }
    return !g_Runtime.paused;
}

/**
 * Suspende el conteo cuando el proveedor entra en readyup.
 * Su estado incluye también la cuenta regresiva previa a live.
 */
public void OnReadyUpInitiate()
{
    HandleReadyUpForward(true, "readyup_start");
}

/** Confirma la salida de readyup antes de recoger muestras nuevas con gracia. */
public void OnRoundIsLive()
{
    HandleReadyUpForward(false, "readyup_live");
}

/**
 * Descarta historial y muestras públicas al recibir una transición de readyup.
 *
 * @param inReady      Estado comunicado por el proveedor.
 * @param reason       Motivo incluido en el diagnóstico del reinicio.
 */
void HandleReadyUpForward(bool inReady, const char[] reason)
{
    g_Runtime.inReady = inReady;
    g_Runtime.readyUpNeedsSync = true;
    ResetAll(GetEngineTime(), reason, SpeedWatchReason_ReadyUp);
    DebugLog(DEBUG_LIFECYCLE, "lifecycle", "event=readyup_forward in_ready=%d reason=%s", inReady, reason);
    g_Log.Flush();
    FlushDetectionEvents();
}

/**
 * Reconcilia readyup si su biblioteca está presente y garantiza IsInReady.
 * Sin proveedor, permite continuar; con estado desconocido, suspende el conteo.
 *
 * @param now          Tiempo real del motor usado para aplicar gracia.
 * @return             True si está sincronizado y fuera de readyup.
 */
bool bReconcileReadyUp(float now)
{
    bool inReady = false;
    if (g_Runtime.hasReadyUp)
    {
        inReady = IsInReady();
    }
    if (g_Runtime.readyUpNeedsSync || inReady != g_Runtime.inReady)
    {
        g_Runtime.inReady = inReady;
        g_Runtime.readyUpNeedsSync = false;
        ResetAll(now, inReady ? "readyup_sync_active" : "readyup_sync_resume",
            inReady ? SpeedWatchReason_ReadyUp : SpeedWatchReason_DependencyChanged);
        DebugLog(DEBUG_LIFECYCLE, "lifecycle", "event=readyup_sync library=%d in_ready=%d late_load=%d",
            g_Runtime.hasReadyUp, inReady, g_Runtime.lateLoad);
        return false;
    }
    return !g_Runtime.inReady;
}

/**
 * Confirma el modo base cuando cambió el mapa, ronda o proveedor.
 * Sin Left4DHooks o con modo desconocido, mantiene los eventos como respaldo.
 * El native devuelve un valor almacenado; no se consulta por comando.
 *
 * @param now          Tiempo real del motor para descartar muestras anteriores.
 * @return             True si no había una sincronización de modo pendiente.
 */
bool bReconcileGameMode(float now)
{
    if (!g_Runtime.modeNeedsSync)
    {
        return true;
    }
    int gameMode = GAMEMODE_UNKNOWN;
    if (g_Runtime.hasLeft4DHooks)
    {
        gameMode = L4D_GetGameModeType();
    }
    g_Runtime.gameMode = gameMode;
    g_Runtime.modeNeedsSync = false;
    ResetAll(now, "game_mode_sync", SpeedWatchReason_DependencyChanged);
    DebugLog(DEBUG_LIFECYCLE, "lifecycle", "event=game_mode_sync left4dhooks_library=%d game_mode=%d",
        g_Runtime.hasLeft4DHooks, gameMode);
    return false;
}

/**
 * Reconcilia los tres proveedores sin que una exclusión impida sincronizar otra.
 *
 * @param now          Tiempo real del motor de esta evaluación.
 * @return             True con modo sincronizado y fuera de pausa y readyup.
 */
bool bReconcileObservation(float now)
{
    bool modeAllows = bReconcileGameMode(now);
    bool pauseAllows = bReconcilePause(now);
    bool readyUpAllows = bReconcileReadyUp(now);
    return modeAllows && pauseAllows && readyUpAllows;
}
