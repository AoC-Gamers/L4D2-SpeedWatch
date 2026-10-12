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
con fecha/hora, categoría, evento y campos técnicos. No se envían al chat.

## ConVars y flags

La activación y las categorías se controlan mediante **ConVars**, sin comandos
de debug registrados. Desde consola de servidor/RCON o en el cfg:

```text
sm_speedwatch_debug "1"           // Activar debug
sm_speedwatch_debug_flags "15"    // General + lifecycle + samples + detections
sm_speedwatch_debug_flags "12"    // Solo samples + detections
sm_speedwatch_debug_flags "31"    // Todas, incluye cada comando
sm_speedwatch_debug_flags "0"     // Ninguna categoría de detalle
sm_speedwatch_debug "0"           // Desactivar debug
```

| Flag | Categoría | Contenido |
| --- | --- | --- |
| `1` | `general` | Arranque y cambios del detector |
| `2` | `lifecycle` | Entrada/salida, cambios de estado, tracking y resets |
| `4` | `samples` | Validez global, ticks, tiempo real, timescale; comandos, ratio, exceso, gracia y racha por humano |
| `8` | `detections` | Evolución de sospechas, muestras requeridas y cooldown |
| `16` | `commands` | Una línea por callback de humano con mapa y observación disponibles, fuera de pausa/readyup/sincronización, incluido cuando no está en tracking; cmdnum, tick del cliente y contador |

Las flags se **suman**. Elegir flags no activa debug por sí solo. El default
`15` excluye la traza por comando; `16`/`31` genera mucho I/O y afecta al CPU.
Conviene usar esa traza solo para capturas cortas y desactivarla al terminar.
`cmdnum` y el tick del cliente solo se registran para diagnóstico; no cambian
la regla de detección.

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
copiar sus valores ni registrar hooks de cambio. La siguiente comprobación usa
los valores actuales; no se generan marcadores de configuración/parada.
La máscara `0` silencia las categorías de detalle.
`sm_speedwatch_debug 0` apaga solo el diagnóstico; conserva las detecciones.

## Escritura y fallos

Se mantiene un único handle abierto. Las escrituras usan buffering y se hace
flush inmediatamente por detección, al terminar cada evaluación de 1 s, al terminar mapa
y al descargar. El timer depende de la simulación: durante una pausa el flush
periódico puede demorarse. Cambiar las ConVars de debug no fuerza un flush.
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
