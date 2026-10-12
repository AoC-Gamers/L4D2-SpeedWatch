/**
 * API pública de L4D2 SpeedWatch. GPL-3.0-or-later.
 * El proveedor observa cadencia de comandos y comunica sospechas sin sancionar.
 */
#if defined _l4d2_speedwatch_included
    #endinput
#endif
#define _l4d2_speedwatch_included

/** Transiciones de un episodio; Recovered e Interrupted lo terminan. */
enum SpeedWatchDetectionState
{
    SpeedWatchDetection_Active = 0,
    SpeedWatchDetection_Recovered,
    SpeedWatchDetection_Interrupted
};

/** Causa del cambio; una interrupción nunca acredita cadencia normal. */
enum SpeedWatchDetectionReason
{
    SpeedWatchReason_None = 0,        /**< Inicio al alcanzar el umbral de sospecha. */
    SpeedWatchReason_NormalCadence,   /**< Período consecutivo de muestras válidas dentro del límite. */
    SpeedWatchReason_Pause,
    SpeedWatchReason_ReadyUp,
    SpeedWatchReason_Death,
    SpeedWatchReason_TeamChanged,
    SpeedWatchReason_Disconnected,
    SpeedWatchReason_ClientUnavailable,
    SpeedWatchReason_RoundEnded,
    SpeedWatchReason_RoundStarted,
    SpeedWatchReason_MapEnded,
    SpeedWatchReason_MapStarted,
    SpeedWatchReason_DetectorDisabled,
    SpeedWatchReason_SettingsChanged,
    SpeedWatchReason_InvalidSample,
    SpeedWatchReason_DependencyChanged,
    SpeedWatchReason_GameModeChanged,
    SpeedWatchReason_PluginUnloaded,
    SpeedWatchReason_ObservationReset
};

/**
 * Notifica el inicio o cierre de un episodio, independientemente del cooldown de chat.
 * Active se emite una vez al alcanzar el umbral; después llega un único terminal.
 * Recovered exige muestras válidas, fuera de gracia y con comandos dentro del límite
 * durante sm_speedwatch_recovery_time. No demuestra que un cheat se desactivó.
 * Interrupted indica pérdida de observación y nunca equivale a Recovered.
 * Identidad capturada al iniciar; AccountID 0 indica identidad no validada.
 * El estado interno cambia antes de notificar y la notificación no se puede vetar.
 * Los cambios anidados se encolan para terminar el forward actual antes del siguiente.
 * No reproduce episodios anteriores para un consumidor que se carga tarde.
 * Revalidar userid antes de usar client; el jugador puede haber salido o cambiado.
 *
 * @param client       Slot original del episodio.
 * @param accountId    AccountID capturado al comenzar, o 0.
 * @param userId       Identificador de la conexión original.
 * @param state        Active, Recovered o Interrupted.
 * @param reason       None para Active; NormalCadence para Recovered; causa de interrupción.
 */
forward void SpeedWatch_OnDetectionStateChanged(int client, int accountId, int userId,
    SpeedWatchDetectionState state, SpeedWatchDetectionReason reason);

/**
 * Última muestra evaluada; no es un historial ni una medición de velocidad física.
 * AccountID es el identificador Steam de 32 bits; 0 indica identidad no validada.
 * engineTime usa GetEngineTime(), en segundos, y no es una fecha Unix.
 */
enum struct SpeedWatchSample
{
    int client;                  /**< Slot del jugador al tomar la muestra. */
    int accountId;               /**< AccountID validado o 0 si no está disponible. */
    int userId;                  /**< Identificador de esta conexión; permite revalidar el slot. */
    float engineTime;            /**< Tiempo real del motor al evaluar la muestra. */
    float commandsPerSecond;     /**< Cadencia observada de callbacks de comandos. */
    float ratio;                 /**< Comandos / ticks nominales esperados en la muestra. */
    float excess;                /**< Exceso acumulado, en comandos. */
    int consecutiveSamples;      /**< Racha actual de muestras sospechosas. */
    bool inGrace;                /**< La muestra está dentro del período de gracia. */
}

/**
 * Copia la última muestra vigente de un humano vivo, incluyendo muestras en gracia.
 * Devuelve false sin mapa, tras cierre de observación, durante pausa/readyup/
 * sincronización, con detector desactivado, sin muestra,
 * muestra de más de 2 s, conexión inválida o tras un reinicio del historial.
 * Los datos pertenecen al instante de evaluación, no al instante de consulta.
 *
 * @param client       Slot entre 1 y MaxClients.
 * @param sample       Salida completa; queda a cero si retorna false.
 * @return             True si hay una muestra vigente para esa conexión.
 * @error              Índice de cliente fuera del rango 1..MaxClients.
 */
native bool SpeedWatch_GetClientSample(int client, SpeedWatchSample sample);

/**
 * Notifica una alerta tras alcanzar el umbral y respetar el cooldown por conexión.
 * Se emite después de registrar la alerta y enviarla al chat. No se puede cancelar.
 * Los valores son una copia de la muestra que originó la alerta.
 * Para trabajo diferido, guardar AccountID y userid; revalidar el slot antes de usarlo.
 * Otro consumidor podría desconectar al jugador antes de que llegue este callback.
 *
 * @param client               Slot del sospechoso al producirse la detección.
 * @param accountId            AccountID validado; 0 si aún no está disponible.
 * @param userId               Identificador de la conexión original.
 * @param commandsPerSecond    Cadencia de comandos observada.
 * @param ratio                Relación entre comandos y ticks nominales esperados.
 * @param excess               Exceso acumulado en comandos.
 * @param consecutiveSamples   Racha que alcanzó el umbral configurado.
 */
forward void SpeedWatch_OnDetection(int client, int accountId, int userId,
    float commandsPerSecond, float ratio, float excess, int consecutiveSamples);

public SharedPlugin __pl_l4d2_speedwatch =
{
    name = "l4d2_speedwatch",
    file = "l4d2_speedwatch.smx",
#if defined REQUIRE_PLUGIN
    required = 1,
#else
    required = 0,
#endif
};

#if !defined REQUIRE_PLUGIN
/** Marca el native como opcional cuando el consumidor no exige el proveedor. */
public void __pl_l4d2_speedwatch_SetNTVOptional()
{
    MarkNativeAsOptional("SpeedWatch_GetClientSample");
}
#endif
