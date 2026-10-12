/**
 * L4D2 SpeedWatch: observational command-rate detection plugin.
 * Copyright (C) 2026. Licensed under GPL-3.0-or-later.
 * Independently implemented; SMAC's command-budget approach is a design reference.
 */
#pragma semicolon 1
#pragma newdecls required

#include <sourcemod>
#include <sdktools>
#include <l4d2_speedwatch>

// Las APIs de los tres proveedores son opcionales al cargar.
#undef REQUIRE_PLUGIN
#include <pause>
#include <readyup>
#include <left4dhooks>
#define REQUIRE_PLUGIN

public Plugin myinfo =
{
    name        = "L4D2 SpeedWatch",
    author      = "Lechuga",
    description = "Reports sustained excess movement commands; never blocks or punishes",
    version     = "0.8.0",
    url         = "https://github.com/AoC-Gamers/L4D2-SpeedWatch"
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
    bool mapLoaded;             /**< Disponibilidad del mapa; no representa una ronda live. */
    bool observationEnded;      /**< Cierre lógico hasta la siguiente ronda o mapa. */
    bool sampleValid;           /**< Validez de la última evaluación, independiente del mapa. */
    int  observationGeneration; /**< Invalida una evaluación tras callbacks reentrantes. */
    bool dispatchingDetectionEvents;
    bool hasPause;
    bool hasReadyUp;
    bool hasLeft4DHooks;
    bool pauseNeedsSync;
    bool readyUpNeedsSync;
    bool modeNeedsSync;
    int  gameMode; /**< Modo base confirmado; GAMEMODE_UNKNOWN permite el respaldo. */
    bool paused;
    bool inReady;

    /** Inicializa el contexto y exige sincronizar los tres proveedores. */
    void Reset(){
        this.lateLoad                   = false;
        this.mapLoaded                  = false;
        this.observationEnded           = false;
        this.sampleValid                = false;
        this.observationGeneration      = 0;
        this.dispatchingDetectionEvents = false;
        this.hasPause                   = false;
        this.hasReadyUp                 = false;
        this.hasLeft4DHooks             = false;
        this.pauseNeedsSync             = true;
        this.readyUpNeedsSync           = true;
        this.modeNeedsSync              = true;
        this.gameMode                   = GAMEMODE_UNKNOWN;
        this.paused                     = false;
        this.inReady                    = false; }

/**
 * Detecta bibliotecas que garantizan sus respectivos natives.
 * Difiere la consulta de pausa, readyup y modo hasta una reconciliación segura.
 */
void DetectLibraries()
{
    this.hasPause         = LibraryExists("pause");
    this.hasReadyUp       = LibraryExists("readyup");
    this.hasLeft4DHooks   = LibraryExists("left4dhooks");
    this.pauseNeedsSync   = true;
    this.readyUpNeedsSync = true;
    this.modeNeedsSync    = true;
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
        this.hasPause       = available;
        this.pauseNeedsSync = true;
    }
    else if (StrEqual(name, "readyup"))
    {
        this.hasReadyUp       = available;
        this.readyUpNeedsSync = true;
    }
    else if (StrEqual(name, "left4dhooks"))
    {
        this.hasLeft4DHooks = available;
        this.gameMode       = GAMEMODE_UNKNOWN;
        this.modeNeedsSync  = true;
    }
}
}

PluginRuntimeState g_Runtime;

ConVar             g_cvDebug;
ConVar             g_cvDebugMask;

ConVar             g_cvEnabled;
ConVar             g_cvRate;
ConVar             g_cvBurst;
ConVar             g_cvSamples;
ConVar             g_cvGrace;
ConVar             g_cvCooldown;
ConVar             g_cvRecoveryTime;
ConVar             g_cvPublic;
ConVar             g_cvTimescale;

// Módulos privados del mismo plugin; las ConVars y el runtime se declaran arriba.
#include "l4d2_speedwatch/logging.sp"
#include "l4d2_speedwatch/detector.sp"
#include "l4d2_speedwatch/integrations.sp"

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
        strcopy(error, errMax, "This plugin requires Left 4 Dead 2.");
        return APLRes_Failure;
    }
    g_Runtime.Reset();
    g_Runtime.lateLoad = late;
    RegPluginLibrary("l4d2_speedwatch");
    CreateNative("SpeedWatch_GetClientSample", Native_GetClientSample);
    g_hDetectionForward      = new GlobalForward("SpeedWatch_OnDetection", ET_Ignore,
                                                 Param_Cell, Param_Cell, Param_Cell, Param_Float, Param_Float, Param_Float, Param_Cell);
    g_hDetectionStateForward = new GlobalForward("SpeedWatch_OnDetectionStateChanged", ET_Ignore,
                                                 Param_Cell, Param_Cell, Param_Cell, Param_Cell, Param_Cell);
    g_DetectionEvents        = new ArrayList(sizeof(DetectionStateEvent));
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
    g_cvEnabled      = CreateConVar("sm_speedwatch_enable", "1", "Enable observation", FCVAR_NONE, true, 0.0, true, 1.0);
    g_cvRate         = CreateConVar("sm_speedwatch_rate", "1.10", "Allowed commands / nominal server ticks", FCVAR_NONE, true, 1.02, true, 3.0);
    g_cvBurst        = CreateConVar("sm_speedwatch_burst", "2.0", "Excess-command buffer in nominal tick seconds", FCVAR_NONE, true, 0.5, true, 10.0);
    g_cvSamples      = CreateConVar("sm_speedwatch_samples", "3", "Consecutive excess samples required above buffer", FCVAR_NONE, true, 2.0, true, 20.0);
    g_cvGrace        = CreateConVar("sm_speedwatch_grace", "5.0", "Grace after reset or first alive sample", FCVAR_NONE, true, 2.0, true, 30.0);
    g_cvCooldown     = CreateConVar("sm_speedwatch_cooldown", "30.0", "Minimum seconds between alerts per client", FCVAR_NONE, true, 10.0, true, 300.0);
    g_cvRecoveryTime = CreateConVar("sm_speedwatch_recovery_time", "5.0", "Consecutive valid normal-cadence seconds to end a detection episode", FCVAR_NONE, true, 1.0, true, 60.0);
    g_cvPublic       = CreateConVar("sm_speedwatch_public", "0", "0: admin chat; 1: everyone's chat", FCVAR_NONE, true, 0.0, true, 1.0);
    g_cvTimescale    = FindConVar("host_timescale");
    g_cvDebug        = CreateConVar("sm_speedwatch_debug", "0", "Enable diagnostic file debug; detection alerts are always logged", FCVAR_NONE, true, 0.0, true, 1.0);
    g_cvDebugMask    = CreateConVar("sm_speedwatch_debug_flags", "15", "Debug flags: 1 general, 2 lifecycle, 4 samples, 8 detections, 16 commands", FCVAR_NONE, true, 0.0, true, float(DEBUG_ALL));
    g_Log.Init();
    DebugLog(DEBUG_GENERAL, "general", "event=plugin_start version=0.8.0 debug=%d flags=%d",
             g_cvDebug.BoolValue, g_cvDebugMask.IntValue);

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
    g_Runtime.mapLoaded        = true;
    g_Runtime.pauseNeedsSync   = true;
    g_Runtime.readyUpNeedsSync = true;
    g_Runtime.modeNeedsSync    = true;
    g_Runtime.gameMode         = GAMEMODE_UNKNOWN;
    ResetAll(GetEngineTime(), "map_start", SpeedWatchReason_MapStarted);
    FlushDetectionEvents();
}

/**
 * Retira el mapa e invalida las muestras como respaldo del cierre lógico.
 * Limpia el cierre anterior para el próximo mapa, que todavía no está disponible.
 */
public void OnMapEnd()
{
    g_Runtime.mapLoaded        = false;
    g_Runtime.observationEnded = false;
    g_Runtime.gameMode         = GAMEMODE_UNKNOWN;
    g_Runtime.modeNeedsSync    = true;
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
                                         ? SpeedWatchReason_DetectorDisabled
                                         : SpeedWatchReason_SettingsChanged;
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
        ResetClient(client, GetEngineTime(), StrEqual(name, "player_death") ? SpeedWatchReason_Death : SpeedWatchReason_TeamChanged);
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
    g_Runtime.modeNeedsSync    = true;
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
    ReplyToCommand(client, "[SpeedWatch] debug=%d flags=%d file_ready=%d path=%s",
                   g_cvDebug.BoolValue, g_cvDebugMask.IntValue, g_Log.file != null, g_Log.path);
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
 * Notifica el cierre de episodios activos antes de cerrar el archivo al descargar.
 */
public void OnPluginEnd()
{
    g_Runtime.mapLoaded   = false;
    g_Runtime.sampleValid = false;
    for (int client = 1; client <= MaxClients; client++)
    {
        EndDetectionEpisode(client, SpeedWatchDetection_Interrupted, SpeedWatchReason_PluginUnloaded);
    }
    FlushDetectionEvents();
    DebugLog(DEBUG_LIFECYCLE, "lifecycle", "event=plugin_end");
    g_Log.Close();
}
