/**
 * L4D2 SpeedWatch: observational command-rate prototype.
 * Copyright (C) 2026. Licensed under GPL-3.0-or-later.
 * Independently implemented; SMAC's command-budget approach is a design reference.
 */
#pragma semicolon 1
#pragma newdecls required

#include <sourcemod>
#include <sdktools>

#define SPEEDWATCH_PROVIDER
#include <l4d2_speedwatch>

// Las APIs de los tres proveedores y SDKHooks indirecto son opcionales al cargar.
#undef REQUIRE_PLUGIN
#undef REQUIRE_EXTENSIONS
#undef AUTOLOAD_EXTENSIONS
#include <pause>
#include <readyup>
#include <left4dhooks>
#define AUTOLOAD_EXTENSIONS
#define REQUIRE_EXTENSIONS
#define REQUIRE_PLUGIN

public Plugin myinfo =
{
    name        = "L4D2 SpeedWatch",
    author      = "Lechuga",
    description = "Reports sustained excess movement commands; never blocks or punishes",
    version     = "0.8.0",
    url         = ""
};

// Máscara de diagnóstico: la traza por comando se excluye del valor por defecto.
#define DEBUG_GENERAL    (1 << 0)
#define DEBUG_LIFECYCLE  (1 << 1)
#define DEBUG_SAMPLES    (1 << 2)
#define DEBUG_DETECTIONS (1 << 3)
#define DEBUG_COMMANDS   (1 << 4)
#define DEBUG_DEFAULT    (DEBUG_GENERAL | DEBUG_LIFECYCLE | DEBUG_SAMPLES | DEBUG_DETECTIONS)
#define DEBUG_ALL        (DEBUG_DEFAULT | DEBUG_COMMANDS)

/**
 * Contexto de carga, mapa, observación y bibliotecas opcionales.
 * Los callbacks de biblioteca solo actualizan memoria; cada proveedor mantiene
 * su propia sincronización antes de permitir el conteo.
 */
enum struct PluginRuntimeState
{
    bool lateLoad;
    bool mapLoaded;          /**< Disponibilidad del mapa; no representa una ronda live. */
    bool observationEnded;   /**< Cierre lógico hasta la siguiente ronda o mapa. */
    bool sampleValid;        /**< Validez de la última evaluación, independiente del mapa. */
    int observationGeneration; /**< Invalida una evaluación tras callbacks reentrantes. */
    bool dispatchingDetectionEvents;
    bool hasPause;
    bool hasReadyUp;
    bool hasLeft4DHooks;
    bool pauseNeedsSync;
    bool readyUpNeedsSync;
    bool modeNeedsSync;
    int gameMode;            /**< Modo base confirmado; GAMEMODE_UNKNOWN permite el respaldo. */
    bool paused;
    bool inReady;

    /** Inicializa el contexto y exige sincronizar los tres proveedores. */
    void Reset()
    {
        this.lateLoad = false;
        this.mapLoaded = false;
        this.observationEnded = false;
        this.sampleValid = false;
        this.observationGeneration = 0;
        this.dispatchingDetectionEvents = false;
        this.hasPause = false;
        this.hasReadyUp = false;
        this.hasLeft4DHooks = false;
        this.pauseNeedsSync = true;
        this.readyUpNeedsSync = true;
        this.modeNeedsSync = true;
        this.gameMode = GAMEMODE_UNKNOWN;
        this.paused = false;
        this.inReady = false;
    }

    /**
     * Detecta bibliotecas que garantizan sus respectivos natives.
     * Difiere la consulta de pausa, readyup y modo hasta una reconciliación segura.
     */
    void DetectLibraries()
    {
        this.hasPause = LibraryExists("pause");
        this.hasReadyUp = LibraryExists("readyup");
        this.hasLeft4DHooks = LibraryExists("left4dhooks");
        this.pauseNeedsSync = true;
        this.readyUpNeedsSync = true;
        this.modeNeedsSync = true;
    }

    /**
     * Actualiza solo la biblioteca notificada y solicita sincronizar su estado.
     * Las bibliotecas desconocidas no modifican el contexto.
     *
     * @param name         Nombre de biblioteca notificado por SourceMod.
     * @param available    True al cargar; false al retirar.
     */
    void SetLibraryAvailability(const char[] name, bool available)
    {
        if (StrEqual(name, "pause"))
        {
            this.hasPause = available;
            this.pauseNeedsSync = true;
        }
        else if (StrEqual(name, "readyup"))
        {
            this.hasReadyUp = available;
            this.readyUpNeedsSync = true;
        }
        else if (StrEqual(name, "left4dhooks"))
        {
            this.hasLeft4DHooks = available;
            this.gameMode = GAMEMODE_UNKNOWN;
            this.modeNeedsSync = true;
        }
    }
}

PluginRuntimeState g_Runtime;

/**
 * Un único archivo en append conserva alertas y diagnósticos entre mapas.
 * mode: 1 registra alertas; 2 añade las categorías de debug habilitadas.
 */
enum struct RuntimeLog
{
    int  mode;
    int  mask;
    File file;
    bool initTried;
    bool errorLogged;
    bool dirty;
    bool commandTrace;
    char path[PLATFORM_MAX_PATH];

    /**
     * Comprueba el directorio de logs de SourceMod y lo crea si falta.
     *
     * @return             True si el directorio existe o se creó correctamente.
     */
    bool bEnsureDirectory()
    {
        char directory[PLATFORM_MAX_PATH];
        BuildPath(Path_SM, directory, sizeof(directory), "logs");
        if (DirExists(directory))
        {
            return true;
        }
        return CreateDirectory(directory, 511);
    }

    /**
     * Abre el log en modo append después de asegurar su directorio.
     * Se intenta una sola vez por carga para evitar errores repetidos.
     */
    void Init()
    {
        if (this.initTried)
        {
            return;
        }
        this.initTried = true;
        BuildPath(Path_SM, this.path, sizeof(this.path), "logs/l4d2_speedwatch.log");
        if (!this.bEnsureDirectory())
        {
            this.Fail("directory");
            return;
        }
        this.file = OpenFile(this.path, "a");
        if (this.file == null)
        {
            this.Fail("open");
        }
    }

    /**
     * Comprueba si una categoría de diagnóstico puede escribir al archivo.
     *
     * @param flag         Bit de la categoría de debug.
     * @return             True si debug, categoría y archivo están disponibles.
     */
    bool bDebug(int flag)
    {
        return this.mode == 2 && (this.mask & flag) != 0 && this.file != null;
    }

    /**
     * Añade fecha, categoría y mensaje al archivo mediante buffering.
     * El llamador decide si corresponde un diagnóstico o una alerta obligatoria.
     *
     * @param category     Categoría que identifica el registro.
     * @param message      Mensaje ya formateado.
     */
    void Write(const char[] category, const char[] message)
    {
        if (this.file == null)
        {
            return;
        }
        char timestamp[32];
        FormatTime(timestamp, sizeof(timestamp), "%Y-%m-%d %H:%M:%S");
        if (!this.file.WriteLine("%s [%s] %s", timestamp, category, message))
        {
            this.Fail("write");
            return;
        }
        this.dirty = true;
    }

    /**
     * Vacía el buffer del archivo solamente si existen escrituras pendientes.
     */
    void Flush()
    {
        if (this.file != null && this.dirty)
        {
            if (!this.file.Flush())
            {
                this.Fail("flush");
            }
            this.dirty = false;
        }
    }

    /**
     * Cierra el logger tras un fallo y emite un único error por carga.
     * El detector continúa funcionando aunque el archivo no esté disponible.
     *
     * @param stage        Etapa de la operación que falló.
     */
    void Fail(const char[] stage)
    {
        delete this.file;
        this.commandTrace = false;
        this.dirty        = false;
        if (!this.errorLogged)
        {
            this.errorLogged = true;
            LogError("[SpeedWatch] [logging] event=unavailable stage=%s path=%s", stage, this.path);
        }
    }

    /**
     * Vacía las escrituras pendientes y libera el handle del archivo.
     */
    void Close()
    {
        this.Flush();
        delete this.file;
        this.commandTrace = false;
    }
}

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

RuntimeLog g_Log;
ConVar     g_cvDebug;
ConVar     g_cvDebugMask;

ConVar     g_cvEnabled;
ConVar     g_cvRate;
ConVar     g_cvBurst;
ConVar     g_cvSamples;
ConVar     g_cvGrace;
ConVar     g_cvCooldown;
ConVar     g_cvRecoveryTime;
ConVar     g_cvPublic;
ConVar     g_cvTimescale;

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
 * Valida L4D2, guarda la carga tardía y registra la biblioteca y los natives.
 * Los tres proveedores son opcionales; se detectan en OnAllPluginsLoaded.
 *
 * @param late         Indica si el plugin se carga con el servidor ya iniciado.
 * @return             APLRes_Success en L4D2; APLRes_Failure en otro motor.
 */
public APLRes AskPluginLoad2(Handle myself, bool late, char[] error, int errMax)
{
    if (GetEngineVersion() != Engine_Left4Dead2)
    {
        strcopy(error, errMax, "This prototype requires Left 4 Dead 2.");
        return APLRes_Failure;
    }
    g_Runtime.Reset();
    g_Runtime.lateLoad = late;
    RegPluginLibrary("l4d2_speedwatch");
    CreateNative("SpeedWatch_GetClientSample", Native_GetClientSample);
    g_hDetectionForward = new GlobalForward("SpeedWatch_OnDetection", ET_Ignore,
        Param_Cell, Param_Cell, Param_Cell, Param_Float, Param_Float, Param_Float, Param_Cell);
    g_hDetectionStateForward = new GlobalForward("SpeedWatch_OnDetectionStateChanged", ET_Ignore,
        Param_Cell, Param_Cell, Param_Cell, Param_Cell, Param_Cell);
    g_DetectionEvents = new ArrayList(sizeof(DetectionStateEvent));
    return APLRes_Success;
}

/**
 * Detecta dependencias opcionales cuando el inventario de plugins está listo.
 */
public void OnAllPluginsLoaded()
{
    g_Runtime.DetectLibraries();
}

/**
 * Marca bibliotecas opcionales sin llamar a sus natives en este callback.
 */
public void OnLibraryAdded(const char[] name)
{
    g_Runtime.SetLibraryAvailability(name, true);
}

/**
 * Invalida capacidades retiradas y exige sincronizar antes de volver a contar.
 */
public void OnLibraryRemoved(const char[] name)
{
    g_Runtime.SetLibraryAvailability(name, false);
}

/**
 * Sincroniza los proveedores una vez aplicada la configuración del mapa.
 * Puede actualizar su contexto con la observación cerrada sin reabrirla.
 */
public void OnConfigsExecuted()
{
    if (g_Runtime.mapLoaded)
    {
        bReconcileObservation(GetEngineTime());
        FlushDetectionEvents();
    }
}

/**
 * Configura ConVars, log, eventos y el único timer compartido del detector.
 * Reconstruye la presencia de humanos existentes solo durante carga tardía.
 */
public void OnPluginStart()
{
    LoadTranslations("l4d2_speedwatch.phrases");
    g_cvEnabled   = CreateConVar("sm_speedwatch_enable", "1", "Enable observation", FCVAR_NONE, true, 0.0, true, 1.0);
    g_cvRate      = CreateConVar("sm_speedwatch_rate", "1.10", "Allowed commands / nominal server ticks", FCVAR_NONE, true, 1.02, true, 3.0);
    g_cvBurst     = CreateConVar("sm_speedwatch_burst", "2.0", "Excess-command buffer in nominal tick seconds", FCVAR_NONE, true, 0.5, true, 10.0);
    g_cvSamples   = CreateConVar("sm_speedwatch_samples", "3", "Consecutive excess samples required above buffer", FCVAR_NONE, true, 2.0, true, 20.0);
    g_cvGrace     = CreateConVar("sm_speedwatch_grace", "5.0", "Grace after reset or first alive sample", FCVAR_NONE, true, 2.0, true, 30.0);
    g_cvCooldown  = CreateConVar("sm_speedwatch_cooldown", "30.0", "Minimum seconds between alerts per client", FCVAR_NONE, true, 10.0, true, 300.0);
    g_cvRecoveryTime = CreateConVar("sm_speedwatch_recovery_time", "5.0", "Consecutive valid normal-cadence seconds to end a detection episode", FCVAR_NONE, true, 1.0, true, 60.0);
    g_cvPublic    = CreateConVar("sm_speedwatch_public", "0", "0: admin chat; 1: everyone's chat", FCVAR_NONE, true, 0.0, true, 1.0);
    g_cvTimescale = FindConVar("host_timescale");
    g_cvDebug     = CreateConVar("sm_speedwatch_debug", "0", "Enable diagnostic file debug; detection alerts are always logged", FCVAR_NONE, true, 0.0, true, 1.0);
    g_cvDebugMask = CreateConVar("sm_speedwatch_debug_flags", "15", "Debug flags: 1 general, 2 lifecycle, 4 samples, 8 detections, 16 commands", FCVAR_NONE, true, 0.0, true, float(DEBUG_ALL));
    g_Log.Init();
    g_Log.mode         = g_cvDebug.BoolValue ? 2 : 1;
    g_Log.mask         = g_cvDebugMask.IntValue;
    g_Log.commandTrace = g_Log.bDebug(DEBUG_COMMANDS);
    DebugLog(DEBUG_GENERAL, "general", "event=plugin_start version=0.8.0 mode=%d mask=%d", g_Log.mode, g_Log.mask);
    g_cvDebug.AddChangeHook(OnLogSettingChanged);
    g_cvDebugMask.AddChangeHook(OnLogSettingChanged);

    g_cvEnabled.AddChangeHook(OnDetectorSettingChanged);
    g_cvRate.AddChangeHook(OnDetectorSettingChanged);
    g_cvBurst.AddChangeHook(OnDetectorSettingChanged);
    g_cvSamples.AddChangeHook(OnDetectorSettingChanged);
    g_cvGrace.AddChangeHook(OnDetectorSettingChanged);
    g_cvRecoveryTime.AddChangeHook(OnDetectorSettingChanged);

    HookEvent("player_death", OnClientStateChanged, EventHookMode_Post);
    HookEvent("player_team", OnClientStateChanged, EventHookMode_Post);
    HookEvent("round_start", OnRoundStart, EventHookMode_PostNoCopy);
    HookEvent("scavenge_round_start", OnRoundStart, EventHookMode_PostNoCopy);
    HookEvent("round_end", OnObservationEnd, EventHookMode_PostNoCopy);
    HookEvent("map_transition", OnObservationEnd, EventHookMode_PostNoCopy);
    HookEvent("mission_lost", OnObservationEnd, EventHookMode_PostNoCopy);
    HookEvent("finale_win", OnObservationEnd, EventHookMode_PostNoCopy);
    HookEvent("versus_match_finished", OnObservationEnd, EventHookMode_PostNoCopy);
    HookEvent("scavenge_round_halftime", OnObservationEnd, EventHookMode_PostNoCopy);
    HookEvent("scavenge_round_finished", OnObservationEnd, EventHookMode_PostNoCopy);
    HookEvent("scavenge_match_finished", OnObservationEnd, EventHookMode_PostNoCopy);
    RegAdminCmd("sm_speedwatch_status", OnStatusCommand, ADMFLAG_GENERIC, "Show latest command-rate observations in console");

    if (g_Runtime.lateLoad)
    {
        for (int client = 1; client <= MaxClients; client++)
        {
            g_bHuman[client] = IsClientInGame(client) && !IsFakeClient(client);
        }
    }
    ResetAll(GetEngineTime(), "plugin_start");
    CreateTimer(1.0, OnSampleTimer, _, TIMER_REPEAT);
    AutoExecConfig(true, "l4d2_speedwatch");
}

/**
 * Confirma que el mapa está cargado y solicita sincronizar los tres proveedores.
 * SourceMod también lo anuncia al cargar tarde con un mapa disponible.
 * No sobrescribe un cierre de ronda observado antes de este callback.
 */
public void OnMapStart()
{
    g_Runtime.mapLoaded = true;
    g_Runtime.pauseNeedsSync = true;
    g_Runtime.readyUpNeedsSync = true;
    g_Runtime.modeNeedsSync = true;
    g_Runtime.gameMode = GAMEMODE_UNKNOWN;
    ResetAll(GetEngineTime(), "map_start", SpeedWatchReason_MapStarted);
    FlushDetectionEvents();
}

/**
 * Retira el mapa e invalida las muestras como respaldo del cierre lógico.
 * Limpia el cierre anterior para el próximo mapa, que todavía no está disponible.
 */
public void OnMapEnd()
{
    g_Runtime.mapLoaded = false;
    g_Runtime.observationEnded = false;
    g_Runtime.gameMode = GAMEMODE_UNKNOWN;
    g_Runtime.modeNeedsSync = true;
    ResetAll(GetEngineTime(), "map_end", SpeedWatchReason_MapEnded);
    g_Log.Flush();
    FlushDetectionEvents();
}

/**
 * Inicializa un slot para su nueva conexión y aplica el período de gracia.
 */
public void OnClientPutInServer(int client)
{
    g_bHuman[client]    = !IsFakeClient(client);
    g_NextAlert[client] = 0.0;
    DebugLog(DEBUG_LIFECYCLE, "lifecycle", "event=client_enter slot=%d userid=%d human=%d", client, GetClientUserId(client), g_bHuman[client]);
    ResetClient(client, GetEngineTime(), SpeedWatchReason_ClientUnavailable);
    FlushDetectionEvents();
}

/**
 * Limpia el slot para que otra conexión no herede contadores ni cooldown.
 */
public void OnClientDisconnect(int client)
{
    DebugLog(DEBUG_LIFECYCLE, "lifecycle", "event=client_leave slot=%d human=%d", client, g_bHuman[client]);
    g_bHuman[client]    = false;
    g_NextAlert[client] = 0.0;
    ResetClient(client, GetEngineTime(), SpeedWatchReason_Disconnected);
    FlushDetectionEvents();
}

/**
 * Reinicia las muestras cuando cambia una regla de detección.
 * Evita mezclar contadores recogidos con configuraciones distintas.
 */
public void OnDetectorSettingChanged(ConVar convar, const char[] oldValue, const char[] newValue)
{
    char name[64];
    convar.GetName(name, sizeof(name));
    DebugLog(DEBUG_GENERAL, "general", "event=detector_setting name=%s old=%s new=%s", name, oldValue, newValue);
    SpeedWatchDetectionReason reason = convar == g_cvEnabled && !g_cvEnabled.BoolValue
        ? SpeedWatchReason_DetectorDisabled : SpeedWatchReason_SettingsChanged;
    ResetAll(GetEngineTime(), "detector_setting", reason);
    FlushDetectionEvents();
}

/**
 * Descarta el historial del jugador tras muerte o cambio de equipo.
 * Resuelve el userid del evento para evitar depender de un slot antiguo.
 */
public void OnClientStateChanged(Event event, const char[] name, bool dontBroadcast)
{
    int client = GetClientOfUserId(event.GetInt("userid"));
    if (client > 0)
    {
        DebugLog(DEBUG_LIFECYCLE, "lifecycle", "event=client_state trigger=%s slot=%d userid=%d", name, client, event.GetInt("userid"));
        ResetClient(client, GetEngineTime(), StrEqual(name, "player_death")
            ? SpeedWatchReason_Death : SpeedWatchReason_TeamChanged);
        FlushDetectionEvents();
    }
}

/**
 * Reabre la observación con historial nuevo al iniciar una ronda o mitad.
 * No declara live ni omite las exclusiones de pausa, readyup o simulación.
 */
public void OnRoundStart(Event event, const char[] name, bool dontBroadcast)
{
    g_Runtime.observationEnded = false;
    // Confirma readyup aunque esta transición del proveedor no emita forward.
    g_Runtime.readyUpNeedsSync = true;
    g_Runtime.modeNeedsSync = true;
    // No cambia la elegibilidad por modo ni define el estado competitivo.
    ResetAll(GetEngineTime(), name, SpeedWatchReason_RoundStarted);
    FlushDetectionEvents();
}

/**
 * Cierra la observación al terminar una ronda, mitad, misión o capítulo.
 * El mapa puede seguir cargado; los comandos y la API dejan de consumir muestras.
 * Los cierres repetidos descartan el historial sin volver a habilitar el detector.
 */
public void OnObservationEnd(Event event, const char[] name, bool dontBroadcast)
{
    float now = GetEngineTime();
    if (StrEqual(name, "round_end"))
    {
        // Un evento puede llegar antes del próximo timer tras cargar el proveedor.
        if (g_Runtime.mapLoaded)
        {
            bReconcileGameMode(now);
        }
        if (g_Runtime.hasLeft4DHooks && g_Runtime.gameMode == GAMEMODE_VERSUS)
        {
            DebugLog(DEBUG_LIFECYCLE, "lifecycle", "event=round_end_ignored authority=left4dhooks game_mode=%d", g_Runtime.gameMode);
            FlushDetectionEvents();
            return;
        }
    }
    CloseObservation(now, name);
}

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
 * Descarta el historial y conserva el cierre hasta la próxima ronda o mapa.
 * Ninguna sincronización de proveedor puede reabrir esta ventana por sí sola.
 *
 * @param now          Tiempo real del motor al recibir el cierre.
 * @param reason       Evento o forward que produjo el cierre.
 */
void CloseObservation(float now, const char[] reason)
{
    g_Runtime.observationEnded = true;
    ResetAll(now, reason, SpeedWatchReason_RoundEnded);
    DebugLog(DEBUG_LIFECYCLE, "lifecycle", "event=observation_end trigger=%s map_loaded=%d",
        reason, g_Runtime.mapLoaded);
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
 * Con la traza apagada, evita consultas de entidades, natives y formato de texto.
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
    if (g_Log.commandTrace && g_bHuman[client])
    {
        DebugLog(DEBUG_COMMANDS, "commands", "event=command slot=%d userid=%d cmdnum=%d client_tick=%d tracking=%d count=%d",
                 client, GetClientUserId(client), cmdnum, tickcount, g_bMonitor[client], g_Commands[client]);
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
 * Muestra lifecycle, proveedores, logger y últimas mediciones en la consola.
 *
 * @param client       Cliente solicitante; 0 representa la consola del servidor.
 * @param args         Número de argumentos recibidos.
 * @return             Plugin_Handled para consumir el comando.
 */
public Action OnStatusCommand(int client, int args)
{
    float now = GetEngineTime();
    ReplyToCommand(client, "[SpeedWatch] map_loaded=%d observation_ended=%d",
        g_Runtime.mapLoaded, g_Runtime.observationEnded);
    ReplyToCommand(client, "[SpeedWatch] left4dhooks_library=%d game_mode=%d mode_sync_pending=%d",
        g_Runtime.hasLeft4DHooks, g_Runtime.gameMode, g_Runtime.modeNeedsSync);
    ReplyToCommand(client, "[SpeedWatch] pause_library=%d paused=%d pause_sync_pending=%d",
        g_Runtime.hasPause, g_Runtime.paused, g_Runtime.pauseNeedsSync);
    ReplyToCommand(client, "[SpeedWatch] readyup_library=%d in_ready=%d readyup_sync_pending=%d",
        g_Runtime.hasReadyUp, g_Runtime.inReady, g_Runtime.readyUpNeedsSync);
    ReplyToCommand(client, "[SpeedWatch] debug=%d flags=%d log_mode=%d file_ready=%d path=%s",
                   g_cvDebug.BoolValue, g_Log.mask, g_Log.mode, g_Log.file != null, g_Log.path);
    ReplyToCommand(client, "[SpeedWatch] enabled=%d valid_sample=%d tickrate=%.2f allowed_ratio=%.2f buffer=%.1f ticks",
                   g_cvEnabled.BoolValue, g_Runtime.sampleValid, 1.0 / GetTickInterval(), g_cvRate.FloatValue,
                   g_cvBurst.FloatValue / GetTickInterval());
    ReplyToCommand(client, "[SpeedWatch] recovery_time=%.1fs", g_cvRecoveryTime.FloatValue);
    for (int target = 1; target <= MaxClients; target++)
    {
        if (g_bHuman[target] && IsClientInGame(target))
        {
            float grace = g_GraceUntil[target] - now;
            if (grace < 0.0)
            {
                grace = 0.0;
            }
            ReplyToCommand(client, "#%d %N: tracking=%d cmds/s=%.1f ratio=%.2f excess=%.1f samples=%d grace=%.1fs active=%d recovery=%.1fs",
                           GetClientUserId(target), target, g_bMonitor[target], g_LastRate[target], g_LastRatio[target],
                           g_Debt[target], g_Strikes[target], grace, g_Detections[target].active, g_Detections[target].recoveryTime);
        }
    }
    return Plugin_Handled;
}

/**
 * Escribe un diagnóstico solamente si debug y su categoría están habilitados.
 *
 * @param flag         Bit de la categoría que habilita este diagnóstico.
 * @param category     Etiqueta de categoría para el archivo.
 * @param format       Formato del mensaje; los varargs comienzan en posición 4.
 * @param ...          Argumentos para sustituir en el formato.
 */
void DebugLog(int flag, const char[] category, const char[] format, any...)
{
    if (!g_Log.bDebug(flag))
    {
        return;
    }
    char message[768];
    VFormat(message, sizeof(message), format, 4);
    g_Log.Write(category, message);
}

/**
 * Escribe y vacía una alerta sin depender de debug ni de su máscara.
 *
 * @param category     Etiqueta de categoría para el archivo.
 * @param format       Formato del mensaje; los varargs comienzan en posición 3.
 * @param ...          Argumentos para sustituir en el formato.
 */
void DetectionLog(const char[] category, const char[] format, any...)
{
    // Las alertas omiten los filtros de activación y categorías de debug.
    if (g_Log.file == null)
    {
        return;
    }
    char message[768];
    VFormat(message, sizeof(message), format, 3);
    g_Log.Write(category, message);
    g_Log.Flush();
}

/**
 * Actualiza las opciones de diagnóstico y su traza por comando en memoria.
 * Los marcadores de configuración/parada se escriben sin filtro de categoría.
 */
public void OnLogSettingChanged(ConVar convar, const char[] oldValue, const char[] newValue)
{
    int nextMode = g_cvDebug.BoolValue ? 2 : 1;
    if (g_Log.mode == 2 && nextMode != 2)
    {
        g_Log.Write("general", "event=debug_stopped");
    }
    g_Log.mode         = g_cvDebug.BoolValue ? 2 : 1;
    g_Log.mask         = g_cvDebugMask.IntValue;
    g_Log.commandTrace = g_Log.bDebug(DEBUG_COMMANDS);
    if (g_Log.mode == 2)
    {
        char message[128];
        Format(message, sizeof(message), "event=debug_settings mode=%d mask=%d enabled=%d tickrate=%.2f",
               g_Log.mode, g_Log.mask, g_cvEnabled.BoolValue, 1.0 / GetTickInterval());
        g_Log.Write("general", message);
    }
    g_Log.Flush();
}

/**
 * Notifica el cierre de episodios activos antes de cerrar el archivo al descargar.
 */
public void OnPluginEnd()
{
    g_Runtime.mapLoaded = false;
    g_Runtime.sampleValid = false;
    for (int client = 1; client <= MaxClients; client++)
    {
        EndDetectionEpisode(client, SpeedWatchDetection_Interrupted, SpeedWatchReason_PluginUnloaded);
    }
    FlushDetectionEvents();
    DebugLog(DEBUG_LIFECYCLE, "lifecycle", "event=plugin_end");
    g_Log.Close();
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
