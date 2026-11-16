# Implementación de marcadores de persistencia de SpeedWatch

## Contrato implementado en fuentes

SpeedWatch 0.11.0 añade el forward opcional
`SpeedWatch_OnDetectionPersistence(client, accountId, userId, marker, confirmedSeconds)`.
Los forwards de detección, estados y muestras existentes conservan sus firmas.
Los consumidores anteriores ignoran esta adición; Demo debe recompilarse con el
include actualizado para recibirla. No hay cambios en la API binaria del core nativo.

Un episodio empieza con Active. A partir de ese momento, el productor suma solo
las duraciones de ventanas nativas válidas, fuera de gracia, con exceso actual y
racha en el umbral confirmado. Al completar al menos 30 segundos consecutivos
emite un marcador, reinicia ese contador y conserva el mismo episodio. La duración
real notificada puede llegar a 32 segundos por el cierre discreto de las ventanas;
no hay crédito por tiempo de pared, comandos del cliente o ventanas ausentes.
La ventana que abre Active no se cuenta como persistencia posterior.

Cadencia normal, cero comandos o pérdida de la racha confirmada reinician el
contador. La recuperación, una interrupción o reset cierran/invalidan el episodio
y descartan el intervalo parcial. El ordinal empieza en 1 por episodio. La cola
captura identidad/ordinal/duración antes de llamar a consumidores y mantiene el
orden con los terminales incluso ante callbacks reentrantes. Un marcador no
repite Active ni cambia el cooldown de alertas de chat.

## Integración de Demo y tick

Demo valida la identidad actual, ejecución de campaña activa y tracking existente
para SpeedWatch. Reutiliza su `incident_id`: el marcador nunca crea otro incidente
ni reconstruye un Active perdido antes de una campaña o durante una recarga.
Los ordinales repetidos o fuera de orden se ignoran. El marcador no prolonga
`sm_bs_demo_speedwatch_max_duration` ni suprime los límites de captura existentes.

Cada marcador admitido crea un `event_id` nuevo en el timeline. La secuencia y
`recording_tick` se obtienen de la grabación SourceTV propia y confirmada, con
owner, instancia y archivo coincidentes. Si no hay ese ancla o el tick es negativo,
se descarta el marcador y se registra el motivo; no se fabrica un tick ni se
reproduce más tarde con el tick de otra ventana. El próximo marcador real puede
admitirse si la grabación está disponible.

Si el ancla existe pero Core no admite todavía la escritura durable, la cola
existente conserva evento, UUID, secuencia, instante y tick originales para su
reintento. Un replay del ordinal no añade otro evento. Cambiar de segmento dentro
de la misma ejecución conserva el incidente y ancla el siguiente marcador al
segmento actual. Cambiar de episodio restablece identidad y ordinal.

## Transporte compatible y visibilidad

Se reutiliza el contrato actual: `kind=detection`, `cause=speedhack`, el mismo
`incident_id` y distintos `event_id`, instantes y ticks. Solo el primer Active
registra la detección principal; los marcadores son eventos adicionales del timeline.
Los índices de Backend deduplican por evento y nodo, no por incidente y tipo.
Node Agent ya conserva estos eventos por separado y espera el receipt durable
del segmento exacto antes de entregarlos a Backend. No hay cambios de esquema,
endpoints, permisos, sanciones ni política de publicación.

El timeline actual de la página ya puede representar cada evento con su instante
y tick. Los marcadores siguen la privacidad y revisión del incidente: no hacen
público un speedhack no revisado ni multiplican el número de incidentes.

## Coordinación con la refactorización de Frontend/Backend

Estas capas no se modifican en esta implementación. Para una mejora posterior de
presentación, coordinar en el trabajo de refactorización:

1. Mostrar las confirmaciones posteriores del mismo incidente SpeedWatch como
   «Persistencia confirmada» y su tick, conservando ES/EN, permisos y paginación.
2. Mantener separado el conteo de incidentes del número de marcadores. El registro
   principal puede seguir siendo uno aunque existan varios puntos de navegación.
3. No inferir un inicio a partir de la primera fila de una página parcial. Si se
   requiere distinguir explícitamente inicio/persistencia, diseñar un discriminador
   DTO o un nuevo tipo de evento coordinado en OpenAPI, Backend, Agent y UI.
4. No deduplicar el timeline por `incident_id`: cada `event_id` representa una
   confirmación distinta. Los reintentos del mismo evento sí son idempotentes.

## Validación y aceptación

Las pruebas aisladas ejercitan cuerpos de producción del contador, la cola de
forwards y el consumidor Demo: 29/30/60 segundos, duraciones fraccionarias, cortes
por cadencia normal/cero/racha no confirmada, reset, recuperación, nueva identidad,
orden reentrante, UUID compartido, ordinales repetidos, ticks propios, snapshots
no disponibles/ajenos y reintentos que conservan el tick original.

Compilación y estas pruebas no certifican el motor. La aceptación SRCDS requiere
una ejecución autorizada con un episodio de más de 60 segundos: confirmar dos
marcadores del mismo incidente, ticks distintos, ausencia de marcas durante pausa,
readyup o cadencia normal, cierre del segmento y entrega central de los eventos.
Publicación, copia de binarios y reinicios están fuera de este encargo.
