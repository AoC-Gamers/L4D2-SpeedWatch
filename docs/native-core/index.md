# Núcleo nativo de observación

[Índice general](../index.md) · [Evidencia y ABI](evidence.md) · [Validación](validation.md)

La extensión opcional `l4d2_speedwatch_core` observa metadatos de bloques de
usercmds y llamadas a `PlayerRunCommand`. El plugin sigue calculando la sospecha
con su contador SourcePawn y conserva la API pública anterior. Esta implementación
no sustituye la señal calibrada ni mezcla contadores de etapas distintas.

## Flujo y responsabilidades

```text
IServerGameClients::ProcessUsercmds (pre, MRES_IGNORED)
    -> metadatos de bloque -> agregado por participante
PlayerRunCommand (pre, MRES_IGNORED)
    -> intento observado -> agregado independiente
Timer SourcePawn validado -> Pulse -> snapshot inmutable -> API de diagnóstico
OnPlayerRunCmdPre -> detector heredado -> episodios -> logs/chat/API existente
```

La recepción no acredita almacenamiento ni simulación. `numcmds` y `totalcmds`
son sumas de argumentos, no una suma de pasos ejecutados. `totalcmds-numcmds`
permite examinar backups declarados; no otorga crédito temporal. `dropped_packets`
es el argumento del motor, no un conteo propio de paquetes UDP. No se lee la cola
`CCommandContext` ni se vuelve a contar su contenido. Se mantiene desconocida la
procedencia de cada llamada a `PlayerRunCommand`; no se atribuyen reconstrucciones
internas al cliente.

## Contrato de ventanas

El único cierre de ventanas nativas es `SpeedWatchCore_Pulse`, invocado una vez
por evaluación válida del timer existente. Los hooks no cierran ventanas y las
consultas no consumen datos. El primer Pulse inicia la ventana; el siguiente
publica el agregado anterior. Solo se conserva el último snapshot por participante:
lectores independientes pueden consultarlo repetidamente y detectar omisiones por
`sample_id` (uint64). No hay recuperación de un backlog. El ID es monotónico por
instancia de extensión; tras recarga cambia la instancia y se invalida el historial.

El tiempo nativo es `steady_clock` en microsegundos, no `curtime`, Unix ni el reloj
`GetEngineTime` de SourcePawn. La muestra contiene inicio, fin, duración, ticks e
intervalo nominal por separado. El servicio valida duración de 0.5–2 segundos,
estabilidad de intervalo y avance de ticks de 80–120% de lo nominal. Las exclusiones
más amplias de simulación, timescale, pausa y readyup siguen siendo del plugin.
Una ventana irregular publica calidad degradada; no se interpreta como normalidad.

Cambiar epoch/configuración, perder observación, resetear cliente o retirar la
extensión invalida las muestras. El plugin conserva los resets y `Interrupted`;
no emite `Recovered` por desaparición de evidencia. El servicio deja de aceptar
observaciones si el controlador no renueva la ventana durante 2.5 segundos. Al
volver, el hueco se publica con mala calidad. Al descargar el controlador se
libera su propiedad y sus registros. Solo un plugin puede controlar Pulse y
SetParticipant; otros consumidores solo consultan.

## API experimental v1

El contrato está en `include/l4d2_speedwatch_core.inc`. Las seis funciones son:
`GetApiVersion`, `GetCapabilities`, `Pulse`, `SetParticipant`, `GetSample` y
`GetStatus`, todas con prefijo `SpeedWatchCore_`. El buffer tiene 48 celdas;
versiones incompatibles, clientes fuera de rango y buffers declarados menores
producen error antes de escribir. Un buffer mayor conserva su cola. El consumidor
debe declarar la capacidad real de su array, como en otros natives de SourceMod.
La VM comprueba direcciones, pero no permite reconstruir el tamaño de un array
arbitrario si el llamador miente sobre su longitud.

`GetSample=false` escribe una cabecera versión/longitud y ceros en el resto. Una
muestra ausente, obsoleta (>2 segundos), de otra conexión o no elegible no se
convierte en una muestra válida de cero actividad. Se serializa campo por campo;
no hay memcpy de estructuras del motor ni punteros en la API.

| Celdas | Contenido y disponibilidad |
| --- | --- |
| 0–4 | Versión, longitud, fuente nativa=1, capacidades, calidad |
| 5–9 | userid, serial, AccountID validado o 0, epoch, generación de participante |
| 10/11 | sample_id uint64 |
| 12/13, 14/15 | inicio/fin monotónicos en microsegundos, uint64 |
| 16–20 | ticks inicio/fin, intervalo y duración (bits float32), equipo |
| 21/22, 23/24, 25/26 | bloques, suma numcmds, suma totalcmds (uint64) |
| 27/28, 29/30, 31/32 | suma dropped_packets, bloques ignore, bloques paused |
| 33/34, 35/36, 37/38 | runCommandAttempts, metadatos descartados, último ID de invocación |
| 39/40, 41 | instante y tick de último bloque |
| 42/43, 44 | instante y tick del último intento |
| 45–47 | Reservadas a cero |

Cada uint64 se representa como dos patrones de 32 bits, low seguido de high; no
se debe convertir una sola celda firmada a contador de 64 bits. Capacidades: `1`
metadatos de bloque, `2` intentos RunCommand, `4` equipo por interfaz pública.
La capacidad global anuncia soporte; cada muestra anuncia los hooks que funcionaron
para ese participante. Un cero de un grupo sin bit no significa una medición cero.
Calidad: `1` metadatos inválidos, `2` saturación, `4` discontinuidad de reloj/intervalo,
`8` ticks irregulares, `32` alta/cambio parcial del participante. El bit `16` queda
reservado a indisponibilidad de hook; actualmente esa pérdida cambia capacidades y
reinicia el registro, sin fabricar un dato. Los contadores se saturan, nunca envuelven.

## Participantes y contexto

El plugin abre registros para humanos vivos en equipo 2/3, después de la gracia de
admisión al seguimiento (la gracia de detección sigue su curso). El core valida
independientemente la elegibilidad mediante `IGamePlayer` e `IPlayerInfo`.
Se conservan infectados fantasma si el motor los considera vivos; no se crea una
regla física para ellos. Espectadores y bots no tienen registros analíticos. El
mapa de slots es ligero y admite hasta 256; una capacidad del servidor mayor se
rechaza explícitamente al cargar. No hay quorum, límite de ocho ni inferencia del
formato por población. Cada nueva identidad, equipo o capacidad abre generación.
La autorización tardía actualiza AccountID sin cambiar la identidad de conexión.

El contexto disponible por ventana es el equipo validado, capturado al admitir
el registro. Las transiciones de muerte/equipo/desconexión existentes lo invalidan;
los hooks también descartan un participante que dejó de ser elegible. Clase,
suelo/aire, agua, escalera, incapacidad, velocidades, desplazamientos y movimientos
forzados permanecen **no disponibles**: no hay bit de contexto físico ni umbrales
físicos. Requieren una capa de resolución y validación runtime adicional. Eso no
suspende el análisis temporal heredado.

## Configuración, degradación y coste

`sm_speedwatch_core_compare 1` recoge diagnóstico nativo experimental; `0` lo
suspende y aplica el reset conservador de configuración. Las alertas siempre
usan `detection_backend=legacy`. No existe selector hacia una señal no calibrada.
`sm_speedwatch_status` muestra disponibilidad, capacidades, participantes, memoria
reservada por el servicio y muestras recibidas con su duración, calidad y edad
desde la primera recepción por SourcePawn (no edad absoluta entre relojes). El
comando no cambia de backend. Debug `samples` registra `native_comparison` una vez
por sample_id, junto a la tasa heredada; sus ventanas se identifican por separado
y no se comparan como si fueran temporalmente idénticas.

La ausencia de extensión, natives incompatibles o pérdida de biblioteca mantiene
el backend heredado. No hay dependencia circular: la extensión no consume la API
del plugin. Si falta el offset `PlayerRunCmd` de SDKTools se conservan los bloques,
con bit de intentos ausente. La carga parcial desmonta hooks y listeners.

Los hooks no hacen disco, red, formateo ni forwards SourcePawn. No asignan memoria
para cada comando; cada participante posee solo acumuladores y un snapshot, sin
capturas detalladas ni colas de tamaño dictado por el cliente. La baja de un
participante puede liberar su registro. El límite de metadatos 65535 protege el
agregado; no bloquea ni cambia la decisión del juego. `GetStatus(1/2)` informa
memoria del servicio/registros, no todo SourceMod ni las reservas de SourceHook.
La caché diagnóstica de SourcePawn mantiene una muestra pequeña por slot.
El forward heredado sigue exportado: permanece su coste de preparación de
argumentos aun cuando el núcleo esté presente. No hay ahorro de CPU demostrado.

## Instalación y rollback

Usar el ZIP de la plataforma x86 correcta: SMX, extensión `.so` o `.dll`, fuentes
permitidas, ambos includes públicos, traducciones, licencia, logs y build-info.
Requiere SourceMod/Metamod compatibles con L4D2 y sus gamedata `sdktools.games`.
No se distribuyen SDKs ni librerías del juego. Se reutiliza el offset por nombre
de SDKTools; no se añade un archivo de gamedata con offsets sin evidencia propia.
Mantener las gamedata oficiales al actualizar el juego y volver a validar los hooks.

Para rollback, descargar el plugin y la extensión, retirar el binario del core y
recargar el SMX: al no encontrar la extensión opcional continúa en modo heredado.
Confirmar status, gracia y API antes de volver a utilizar las alertas. La instalación,
recarga y rollback efectivos siguen pendientes de validación en SRCDS.
