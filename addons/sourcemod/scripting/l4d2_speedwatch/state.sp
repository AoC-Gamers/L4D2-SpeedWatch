/** Rule input; no wire indices or engine clocks are reconstructed by cadence policy. */
enum struct NativeCadenceWindow
{
    int commands;
    float duration;
    float interval;
}

/** Shared internal state. Observations, evaluations and episodes have distinct lifetimes. */
// Muestras de solo lectura para consumidores; cada reinicio invalida su slot.
GlobalForward g_hDetectionForward;
GlobalForward g_hDetectionStateForward;
GlobalForward g_hDetectionPersistenceForward;
#define PERSISTENCE_SECONDS 30.0

/** Episodio por conexión; su identidad se conserva aunque el slot deje de estar disponible. */
enum struct DetectionEpisode
{
    bool active;
    int accountId;
    int userId;
    float recoveryTime;
    float persistenceTime;
    int persistenceMarker;
}

/** Copia inmutable de una transición pendiente de notificar a los consumidores. */
enum struct DetectionStateEvent
{
    int client;
    int accountId;
    int userId;
    SpeedWatchDetectionState state;
    SpeedWatchDetectionReason reason;
    int persistenceMarker; // zero is a state transition; positive is a persistence notification
    float confirmedSeconds;
}

DetectionEpisode g_Detections[MAXPLAYERS + 1];
ArrayList g_DetectionEvents;
SpeedWatchSample g_ClientSamples[MAXPLAYERS + 1];
bool g_bHasSample[MAXPLAYERS + 1];

// Elegibilidad y contadores por slot; se limpian al reutilizar la conexión.
bool       g_bHuman[MAXPLAYERS + 1];
bool       g_bMonitor[MAXPLAYERS + 1];
int        g_Strikes[MAXPLAYERS + 1];
float      g_Debt[MAXPLAYERS + 1];
float      g_GraceUntil[MAXPLAYERS + 1];
float      g_NextAlert[MAXPLAYERS + 1];
// Referencias globales para comparar tiempo real y avance de la simulación.
float      g_LastEngineTime;
float      g_LastInterval;
int        g_LastTick;

/**
 * Comprueba en memoria si se permite recoger comandos o consumir una muestra.
 * No afirma que la última evaluación sea válida; eso lo indica sampleValid.
 * No consulta bibliotecas, entidades ni natives de los proveedores.
 *
 * @return             True con mapa disponible, observación abierta y sin exclusiones.
 */
