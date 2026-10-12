# Episodios de detección e integración con un grabador

[Índice de documentación](index.md) · [README](../README.md)

El include, el forward de alertas y el native de consulta se describen en [API pública](api.md).

Desde 0.8.0 se ofrece un flujo independiente de las alertas del chat:

```sourcepawn
#include <sourcemod>
#include <l4d2_speedwatch>

public void SpeedWatch_OnDetectionStateChanged(int client, int accountId, int userId,
    SpeedWatchDetectionState state, SpeedWatchDetectionReason reason)
{
    // Asociar el episodio a userid y conservar accountId para los metadatos.
    switch (state)
    {
        case SpeedWatchDetection_Active:
        {
            PrintToServer("Comenzar episodio: userid=%d accountid=%d", userId, accountId);
        }
        case SpeedWatchDetection_Recovered:
        {
            PrintToServer("Cadencia normal: userid=%d; programar cola de grabacion", userId);
        }
        case SpeedWatchDetection_Interrupted:
        {
            PrintToServer("Observacion interrumpida: userid=%d reason=%d", userId, reason);
        }
    }
}
```

| Estado | Emisión | Significado para el grabador |
| --- | --- | --- |
| `SpeedWatchDetection_Active` (`0`) | Una vez cuando se completa el umbral | Abrir un episodio o cancelar una parada pendiente |
| `SpeedWatchDetection_Recovered` (`1`) | Al menos `sm_speedwatch_recovery_time` segundos consecutivos válidos dentro del límite | Cerrar el episodio por cadencia normal y aplicar la cola configurada en el grabador |
| `SpeedWatchDetection_Interrupted` (`2`) | Al perder la observación de un episodio activo | Cerrar el episodio con su motivo; no significa recuperación |

## Ciclo del episodio

Cada `Active` tiene como máximo un terminal: `Recovered` o `Interrupted`.
Tras ese cierre, un nuevo umbral puede abrir otro episodio aunque siga vigente
el cooldown del chat. Las alertas repetidas del forward antiguo no abren episodios
adicionales. El nuevo forward no depende del debug ni del éxito del log.

## Recuperación

La recuperación requiere muestras fuera de gracia, con al menos un comando y
sin superar el límite `expected * sm_speedwatch_rate`. Cero comandos o cualquier
exceso reinician su racha. La duración suma los intervalos válidos medidos por
el timer de 1 s, por lo que el terminal puede llegar algo después del valor
configurado. La deuda acumulada mantiene su cálculo habitual; la recuperación
mide cadencia actual, sin exigir que la deuda histórica haya llegado a cero.
Esta señal acredita un período observado dentro del límite, no que se haya
desactivado un cheat ni que toda forma de speedhack haya desaparecido.

## Motivos de cierre

`Active` lleva `SpeedWatchReason_None`; `Recovered`,
`SpeedWatchReason_NormalCadence`. Una interrupción identifica pausa, readyup,
muerte, cambio de equipo, desconexión, cliente no disponible, inicio/fin de
ronda o mapa, desactivación/cambio de reglas, muestra inválida, cambio de
proveedor/modo, descarga del plugin o reinicio de observación. Los símbolos
`SpeedWatchReason_*` están documentados en el include; utilizar esos símbolos
en vez de números. Las bibliotecas siguen siendo opcionales y sus callbacks
solo marcan estado: un cambio de proveedor se reconcilia en el siguiente punto
seguro. Las señales de pausa y readyup suspenden inmediatamente la observación.

## Identidad y orden de notificación

La identidad se captura al comenzar y se conserva hasta el terminal, incluso
si el AccountID era `0` o la conexión ya salió. No usar `client` sin revalidar
`userId`. El estado interno se actualiza antes del callback. Los cambios
provocados por un consumidor se encolan hasta completar el forward actual,
para que todos reciban `Active` antes de su terminal. Si un consumidor invalida
la observación, el timer abandona esa evaluación. El inicio se notifica antes
de la alerta antigua; si su consumidor pausa/desconecta/reinicia el detector,
no se envía una alerta posterior basada en la muestra que acaba de invalidar.

## Carga tardía y retirada del proveedor

No hay reproducción de eventos anteriores: un consumidor cargado a mitad de
un episodio puede recibir únicamente su terminal. El grabador debe tolerar ese
caso y gestionar la retirada de la biblioteca y una duración máxima propia,
porque un cierre abrupto del proceso no puede entregar forwards. Cambiar
`sm_speedwatch_recovery_time` interrumpe los episodios con `SettingsChanged`,
descarta muestras y aplica gracia, igual que las demás reglas del detector.

## Responsabilidad del grabador

SpeedWatch comunica estados; el grabador decide la cola final y la política de
`Interrupted`. Por ejemplo, puede conservar la grabación durante una pausa,
y cerrarla al desconectar o terminar el mapa. Si graba una demo global, debe
mantener un conjunto de episodios por userid y parar solo al cerrar todos los
que le interesan y vencer su cola. Ante un nuevo `Active`, cancelar esa parada
pendiente. La cola y la duración máxima pertenecen al grabador y no añaden timers
por jugador a SpeedWatch.

Ver [validación de episodios](testing.md#episodios-y-grabación) antes de integrar la parada real.
