# Integraciones opcionales

[Índice de documentación](index.md) · [README](../README.md)

## Biblioteca opcional `left4dhooks`

Consume `L4D_GetGameModeType()`, `L4D_OnGameModeChange(int gamemode)` y
`L4D2_OnEndVersusModeRound_Post()`. `left4dhooks.smx` es opcional. El repositorio
incluye los cinco includes originales necesarios para compilar, con sus cabeceras
de licencia; se excluyen del ZIP de release. El paquete no instala Left4DHooks ni su gamedata. SDKHooks, incluido
indirectamente por esos headers, usa el comportamiento estándar de SourceMod:
extensión requerida con carga automática, aunque `left4dhooks.smx` siga siendo opcional.

- Guarda `hasLeft4DHooks`, `gameMode` y `modeNeedsSync` en `g_Runtime`.
  Modo base: `0` desconocido, `1` Coop, `2` Versus, `4` Survival, `8` Scavenge.
- Las altas/bajas de biblioteca solo actualizan memoria: invalidan el modo y
  solicitan sincronización. No ejecutan natives, timers ni comandos del proveedor.
- Consulta el native únicamente con la biblioteca presente y sincronización
  pendiente, desde cfg, el timer compartido o un evento `round_end` con mapa
  disponible. Descarta la ventana de transición y aplica gracia. No consulta
  el modo por comando ni en cada segundo una vez sincronizado.
- `L4D_OnGameModeChange` acepta directamente el argumento del proveedor,
  descarta las muestras y aplica gracia sin volver a consultar el mismo valor.
  No reabre una observación cerrada ni modifica pause o readyup.
- Con proveedor presente y modo `2`, ignora el evento genérico `round_end` y
  cierra la mitad desde `L4D2_OnEndVersusModeRound_Post`, después del cierre del
  motor. No consume `PostHandled`: un cierre bloqueado no acredita fin de mitad.
  `versus_match_finished` conserva su cierre independiente de match.
- Sin proveedor, con modo desconocido o en otro modo, conserva `round_end` como
  respaldo junto con los demás eventos existentes. Retirar la biblioteca no
  reabre una observación que ya estaba cerrada.
- No añade señales de salida del saferoom, hooks continuos de velocidad ni
  un nuevo gate de live. La autoridad de readyup y la exclusión de pause se conservan.

`sm_speedwatch_status` muestra `left4dhooks_library`, `game_mode` y
`mode_sync_pending`. Debug `2` registra `game_mode_sync`, `game_mode_forward` y
`round_end_ignored`; el cierre del forward queda como
`event=observation_end trigger=versus_mode_round_end`. La flag `4` muestra el
contexto de modo en las evaluaciones omitidas.

Left4DHooks habilita sus detours al escanear los forwards de los plugins.
Si SpeedWatch se carga tarde en un mapa activo y el detour de fin de Versus no
estaba ya habilitado por otro consumidor, ejecutar desde consola del servidor
`sm_l4dhooks_detours` después de cargarlo. En la versión local revisada ese
comando vuelve a escanear y lista los detours. El siguiente inicio de mapa
también hace el escaneo. SpeedWatch no ejecuta automáticamente comandos que
reconfiguren al proveedor. La presencia de la biblioteca y el modo confirmado
no prueban por sí solos que el detour se haya habilitado en esa carga tardía.

## Biblioteca opcional `pause`

Compatible por diseño con la API de `pause.sp` de L4D2-Competitive-Rework:
`IsInPause()`, `OnPause` y `OnUnpause`. `pause.smx` **no es obligatorio** para
cargar SpeedWatch. El repositorio incluye una copia de `pause.inc` para compilar,
con su cabecera de licencia original; el ZIP excluye ese include y no instala el plugin de pausa.

- `OnPause` suspende inmediatamente el conteo y descarta comandos, exceso y
  rachas. Tampoco se escriben trazas por comando durante la pausa.
- `OnUnpause` descarta el historial y aplica la gracia configurada; el siguiente
  reconciliador confirma el estado antes de volver a contar.
- En carga tardía o al cargar la biblioteca, el conteo permanece suspendido
  hasta consultar `IsInPause()` desde `OnConfigsExecuted` o el timer existente.
- Las altas/bajas de biblioteca solo actualizan el estado en memoria. Al retirar
  `pause`, su native se invalida inmediatamente; la siguiente reconciliación
  descarta el historial y vuelve al detector autónomo con gracia.
- La presencia de la biblioteca `pause` garantiza el native `IsInPause()` según
  el contrato del proveedor. Solo lo llama mientras esa biblioteca está presente,
  sin consultas redundantes de `GetFeatureStatus` ni un flag paralelo de capacidad.

La consulta periódica es una vez por evaluación de 1 s, además de la
sincronización al ejecutar cfg. No hay consultas de biblioteca ni de native
por comando. Los forwards permiten cubrir también pausas cortas entre muestras.
Se conserva el cooldown de alertas al pausar/reanudar, sin modificar el motor
ni las ConVars o comandos de `pause.sp`.

`sm_speedwatch_status` muestra `pause_library`, `paused` y
`pause_sync_pending`. La flag de debug `2` registra forwards y sincronizaciones;
la flag `4` registra las muestras omitidas durante pausa o estado pendiente.
Sin `pause`, las pausas manuales o de otros plugins siguen dependiendo de las
comprobaciones generales de tiempo/ticks; `IsInPause()` solo conoce su proveedor.
La compatibilidad en juego y las transiciones de carga/descarga aún requieren
prueba en SRCDS.

## Biblioteca opcional `readyup`

Se integra con `readyup.sp` de L4D2-Competitive-Rework mediante `IsInReady()`,
`OnReadyUpInitiate` y `OnRoundIsLive`. El repositorio incluye una copia de `readyup.inc`
con su cabecera original, excluida del ZIP de release. `readyup.smx` no es obligatorio ni se instala con el
paquete; tampoco se añaden las dependencias que utiliza internamente ese proveedor.

- Al entrar en readyup, suspende inmediatamente conteo, traza por comando,
  acumulación de exceso y alertas. Descarta el historial y las muestras de API.
- La exclusión incluye la cuenta regresiva: `IsInReady()` sigue siendo true hasta
  que el proveedor declara live. Cancelar el countdown conserva la exclusión.
- Al recibir `OnRoundIsLive`, borra el historial y aplica gracia; confirma el
  estado del native antes de volver a recoger muestras.
- Carga tardía, cambio de mapa/ronda y alta/baja de biblioteca solicitan nueva
  sincronización. Los callbacks de biblioteca solo modifican estado en memoria.
- La presencia de la biblioteca `readyup` garantiza el native `IsInReady()` según
  el contrato del proveedor. Solo lo llama mientras esa biblioteca está presente,
  sin consultas redundantes de `GetFeatureStatus` ni un flag paralelo de capacidad.
  Sin biblioteca, continúa con gracia y las demás comprobaciones del detector,
  incluida la integración opcional con pause.
- El timer existente reconcilia pausa y readyup por separado, incluso si una
  exclusión ya está activa. No crea otro timer ni consulta natives por comando.
  Esto cubre también cambios de estado del proveedor que no emiten forward.

`sm_speedwatch_status` incluye `readyup_library`, `in_ready`
y `readyup_sync_pending`. La flag debug `2` registra `readyup_forward` y
`readyup_sync`; la flag `4` registra `observation_sample_skipped` con el estado de
ambas bibliotecas. El cooldown se conserva en las transiciones de readyup.

Durante readyup o sincronización pendiente, `SpeedWatch_GetClientSample` devuelve
false y pone el struct a cero; no se emite `SpeedWatch_OnDetection`. El contrato
público conserva los campos de muestra y la firma del forward. No se expone como
live una fase inferida a partir de `round_start` o de movimiento del jugador.

La matriz de carga, descarga y transiciones está en [pruebas pendientes](testing.md).
