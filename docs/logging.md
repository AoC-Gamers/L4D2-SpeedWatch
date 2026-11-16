# Logs y debug

[Índice de documentación](index.md) · [README](../README.md)

El plugin crea y abre en modo append:

```text
addons/sourcemod/logs/l4d2_speedwatch.log
```

La ruta se resuelve con `Path_SM`, por lo que respeta instalaciones con un
directorio de SourceMod personalizado. El método `RuntimeLog.bEnsureDirectory()`
comprueba si existe `logs/` y lo crea cuando falta; `Init()` lo llama antes de
abrir el archivo. El archivo se crea al cargar el plugin;
sin detecciones y con debug apagado puede quedar vacío. No se trunca al cambiar de mapa ni al
recargar. Todas las líneas de debug habilitadas se escriben en ese archivo,
con fecha/hora, categoría, sesión de carga, evaluación, epoch de observación,
evento y campos técnicos. No se envían al chat.

## ConVars y flags

La activación y las categorías se controlan mediante **ConVars**, sin comandos
de debug registrados. Desde consola de servidor/RCON o en el cfg:

```text
sm_speedwatch_debug "1"           // Activar debug
sm_speedwatch_debug_flags "15"    // General + lifecycle + samples + detections
sm_speedwatch_debug_flags "12"    // Solo samples + detections
sm_speedwatch_debug_flags "31"    // Igual que 15; el bit 16 está reservado
sm_speedwatch_debug_flags "0"     // Ninguna categoría de detalle
sm_speedwatch_debug "0"           // Desactivar debug
```

| Flag | Categoría | Contenido |
| --- | --- | --- |
| `1` | `general` | Arranque y cambios del detector |
| `2` | `lifecycle` | Entrada/salida, cambios de estado, tracking y resets |
| `4` | `samples` | Validez global, ticks, tiempo real, timescale; comandos, ratio, exceso, gracia y racha por humano |
| `8` | `detections` | Evolución de sospechas, muestras requeridas y cooldown |
| `16` | Reservado | Aceptado por compatibilidad de cfg, sin salida por comando desde 0.10.0 |

Las flags se **suman**. Elegir flags no activa debug por sí solo. El default
`15` activa las cuatro categorías disponibles; `31` produce la misma salida.

## Registros obligatorios

Cada detección que alcanza el umbral y emite una alerta (`event=alert`) se
registra **siempre**, incluso con `sm_speedwatch_debug 0` y flags en `0`.
Se guarda fecha/hora, userid, cadencia, ratio, exceso, racha y audiencia de chat,
y se hace flush inmediatamente. El cooldown sigue limitando las alertas
repetidas por conexión. Las transiciones del episodio también se registran siempre
como `event=detection_state`, con client, AccountID, userid, state y reason
(valores numéricos de los enums del include), incluso durante el cooldown. Las sospechas intermedias siguen siendo detalle opcional
de la flag `8`; no se consideran una alerta hasta completar el umbral.

`sm_speedwatch_debug 1` añade las categorías de diagnóstico elegidas. El logger
consulta directamente las ConVars globales al comprobar una categoría, sin
copiar sus valores. La siguiente comprobación usa los valores actuales. Los hooks
de debug y máscara solo emiten contexto cuando queda alguna categoría activa;
no reinician el historial ni modifican las reglas del detector.
La máscara `0` silencia las categorías de detalle.
`sm_speedwatch_debug 0` apaga solo el diagnóstico; conserva las detecciones.

## Escritura y fallos

Se mantiene un único handle abierto. Las escrituras usan buffering y se hace
flush inmediatamente por detección, al terminar cada evaluación de 1 s, al terminar mapa
y al descargar. El timer depende de la simulación: durante una pausa el flush
periódico puede demorarse. Los registros de contexto hacen flush al emitirse.
Si falla la creación, escritura o flush, el detector sigue funcionando, se
deshabilita la salida al archivo y se reporta un solo error por carga. La consulta
`sm_speedwatch_status` muestra `file_ready=0`; tras corregir permisos/espacio,
recargar el plugin para reabrir el archivo.

## Configuración persistente y migración

Las ConVars se pueden cambiar en memoria. Para conservar la configuración entre
reinicios o ejecuciones del cfg por mapa, agregar al cfg existente:

```text
sm_speedwatch_debug "1"
sm_speedwatch_debug_flags "15"
```

Agregar esas dos entradas manualmente si el cfg ya existía. Sustituyen la
configuración de debug de 0.2.0 (`log_mode 2` y `debug_mask`). La ConVar
`sm_speedwatch_log_mode` se retiró en 0.2.2: quitarla de cfg anteriores.
Desde consola de
cliente, un admin autorizado puede usar `sm_cvar sm_speedwatch_debug 1` y
`sm_cvar sm_speedwatch_debug_flags 15`. Sin argumento, la ConVar muestra su
valor en consola de servidor. No hay rotación automática del archivo.

Las pruebas de creación, append, permisos y debug están en [validación](testing.md).

## Diagnóstico del detector nativo

Status informa `detection_backend=native`, disponibilidad, capacidades y ventanas
leídas por el timer. No consume evidencia ni anuncia comandos ejecutados. Ver el
[contrato del núcleo](native-core/index.md) y su [validación](native-core/validation.md).

## Cambios de 0.10.0

El bit 16 se conserva reservado para aceptar cfg anteriores, pero no produce
trazas por comando. Ya no existe el callback SourcePawn de conteo. La categoría
`samples` registra `native_window` (ID, calidad, aceptación, intentos, duración)
con los motivos de aceptación/descarte en esa misma línea. Las alertas usan
exclusivamente ventanas nativas.

## Contexto y correlación del candidato 0.10.0

Todas las líneas llevan `session`, `evaluation` y `observation_epoch`:

- `session` identifica esta carga del plugin (hora, referencia temporal del motor
  y handle); no es un identificador de incidente ni cambia la API pública.
- `evaluation` es el contador del timer, en hexadecimal; vale cero antes de su
  primera evaluación. Varias líneas pueden pertenecer a la misma evaluación.
- `observation_epoch` es la generación global al escribir. Los eventos disparados
  fuera del timer conservan el último contador de evaluación: no significa que
  el evento se haya originado dentro de ese timer.

`native_window`, `client_sample`, `suspicion` y `alert` añaden la identidad de su
ventana cuando existe: `window_epoch`, `generation` del participante y `window`
como `high:low` hexadecimal de 8 dígitos por mitad. `window_available=0` impide
interpretar ceros inventados como una ventana real. El rechazo conserva el ID
observado, incluso si no llega a publicarse una muestra evaluada. El registro
nativo añade `previous_available` y `previous_window` antes de avanzar el cursor.
Una correlación completa usa sesión, userid, epoch, generación e ID de ventana.

`debug_context` se emite al cargar con debug activo, al activar debug/cambiar
su máscara, al comenzar mapa, tras aplicar configuraciones y al reconciliar el
core. Incluye versión, mapa, máscara, señal, disponibilidad/capacidades y estado
pendiente del core, API esperada, activación y umbrales. Se escribe aunque solo
esté seleccionada `samples` o `detections`; con debug apagado, máscara cero o solo
el bit reservado no produce salida. No consulta natives de los proveedores para
reconstruir el contexto. `map=unavailable` y `core_pending=1` expresan que todavía
no hay estado confirmado; los registros posteriores completan el contexto.

## Motivos de descarte de ventanas

`reasons` combina nombres con `|`; `reason_bits` conserva su máscara hexadecimal.
`accepted=1 reasons=none` identifica una ventana aceptada por la validación nativa,
que todavía puede estar dentro de gracia. Los motivos no cambian los umbrales:

| Motivo | Significado |
| --- | --- |
| `header` | API, longitud o identificador de fuente incorrectos |
| `identity` | userid o serial no corresponden a esta conexión |
| `epoch` / `team` | Generación global o equipo no corresponden al contexto actual |
| `capabilities` | Faltan capacidades requeridas en la ventana |
| `timing` | Duración o intervalo fuera de los límites existentes, incluidos NaN/infinitos |
| `counter_range` | Contador de intentos no representable por el detector |
| `first_window` | Primera ventana: prepara el cursor sin evaluar cadencia |
| `generation_changed` | Cambió la generación del participante |
| `duplicate` / `discontinuity` | ID repetido o inicio que no enlaza con el fin anterior |
| `quality` | El core marcó calidad degradada; `quality` conserva sus bits originales |
| `ignored_blocks` / `paused_blocks` | Hay bloques ignorados o pausados |
| `core_not_ready` | El core todavía no permite consultar una ventana válida |
| `sample_unavailable` | GetSample devolvió false; estado 47 distingue ausencia y obsolescencia |

No se añade un segundo evento genérico `native_window_rejected`. Las suspensiones
globales siguen en `observation_sample_skipped`, ahora con disponibilidad, readiness,
pendiente y capacidades del core. Los eventos de muestra no se escriben por comando.

### Corrección del filtro dropped_packets

El motivo `packet_loss` se retiró; su antiguo bit 12 no se reutiliza. Un `dropped`
no nulo puede acompañar `accepted=1 reasons=none`. El dato sigue siendo diagnóstico
high:low y no se suma al contador de intentos ni al presupuesto de detección.
Las ventanas con drops pasan por los mismos umbrales, buffer, racha y gracia que
las demás; esos metadatos no borran el historial por sí solos. Los logs anteriores
a esta corrección pueden contener el motivo retirado.

## Marcadores de persistencia 0.11.0

`event=detection_persistence` es un registro obligatorio por cada intervalo de
al menos 30 segundos consecutivos de exceso confirmado después de Active.
Incluye identidad, ordinal `marker` y `confirmed_seconds`, junto con la correlación
común de sesión/evaluación/epoch. Es independiente del cooldown de chat y no
representa otro incidente. El consumidor Demo aporta el tick real de la grabación.

## Contrato nativo v2

`native_detector_unavailable` se registra aun con debug apagado cuando la
reconciliación no puede habilitar la regla; incluye capacidades requeridas y
presentes. Core ausente o API incompatible impide iniciar el plugin y el error
lo informa SourceMod. `core_instance_changed` interrumpe continuidad.
Status añade `observation_state` según el enum del include. Los motivos de descarte
y la identidad de ventana se conservan; `dropped_packets` sigue sin descartarla.
