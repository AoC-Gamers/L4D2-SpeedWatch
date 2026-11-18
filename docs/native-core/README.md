# Núcleo nativo de observación

[Índice general](../README.md) · [Evidencia y ABI](evidence.md) · [Validación](validation.md)

Desde 0.10.0, `l4d2_speedwatch_core` es la única fuente de evidencia del detector.
La extensión agrega bloques de usercmds e intentos de `PlayerRunCommand`;
SourcePawn aplica umbrales, gracia, episodios y alertas a sus ventanas validadas.
La API pública conserva firmas y unidades. No existe fallback a conteo SourcePawn.

## Flujo y responsabilidades

```text
IServerGameClients::ProcessUsercmds (pre, MRES_IGNORED)
    -> metadatos de bloque -> agregado por participante
PlayerRunCommand (pre, MRES_IGNORED)
    -> intento observado -> agregado independiente
Timer SourcePawn (exclusiones de partida) -> Pulse -> snapshot inmutable
    -> validar continuidad/calidad -> detector de cadencia -> episodios/logs/chat/API
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

## API nativa v2

El contrato está en `include/l4d2_speedwatch_core.inc`. Las seis funciones son:
`GetApiVersion`, `GetCapabilities`, `Pulse`, `SetParticipant`, `GetSample` y
`GetStatus`, todas con prefijo `SpeedWatchCore_`. El buffer tiene 48 celdas;
versiones incompatibles, clientes fuera de rango y buffers declarados menores
producen error antes de escribir. Un buffer mayor conserva su cola. El consumidor
debe declarar la capacidad real de su array, como en otros natives de SourceMod.
La VM comprueba direcciones, pero no permite reconstruir el tamaño de un array
arbitrario si el llamador miente sobre su longitud.

`GetSample=false` escribe versión/longitud y estado en la celda 47; el resto queda a cero. Una
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
| 45/46 | Identidad uint64 de la instancia del core |
| 47 | Estado: 0 ausente, 1 publicado, 2 obsoleto, 3 interrumpido/parcial |

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
suspende por sí sola el análisis de cadencia de intentos.

## Configuración, degradación y coste

Las alertas usan `detection_backend=native signal=run_command_attempts`.
`sm_speedwatch_core_compare` se retiró: quitarla de cfg existentes. El único control
de activación es `sm_speedwatch_enable`. Desde 0.12.0 la extensión es requerida por el loader. La ausencia
impide cargar el SMX y una API incompatible falla explícitamente al iniciar.
Si faltan capacidades, `detector_ready=0`: se interrumpen episodios y no se
publican muestras ni alertas.
No se vuelve al backend anterior. El bit global anuncia soporte; cada ventana debe
confirmar también las tres capacidades (bloques, intentos, equipo).

Se evalúa una ventana una sola vez en el timer. Debe pertenecer al userid/serial,
equipo y epoch actuales, tener duración de 0.5–2 s, contador representable y calidad
cero. Se enlaza el inicio con el fin anterior y se verifica la generación del
participante y un ID de muestra distinto. Primera ventana, huecos, duplicados,
cambios de identidad/capacidades, metadatos inválidos o bloques ignorados/pausados
invalidan el historial y aplican gracia. Los descartes interrumpen
un episodio; nunca lo recuperan. La primera ventana solo prepara el cursor y no
recrea continuamente el participante. La siguiente ventana limpia puede continuar.

`dropped_packets` distinto de cero permanece como contexto diagnóstico; no rechaza
la ventana, no borra deuda/racha y no reinicia gracia por sí solo. No acredita una
cantidad equivalente de paquetes UDP perdidos ni explica su causa. Las ráfagas
legítimas se amortiguan mediante margen, buffer acotado y racha consecutiva: con
los defaults, una o dos ventanas elevadas seguidas de cadencia normal no abren un
episodio. El exceso sostenido sí puede alcanzar el umbral aunque registre drops.
Esto no garantiza ausencia de falsos positivos con cualquier patrón de red;
la calibración en partidas sigue siendo necesaria.

La cadencia usa exclusivamente `runCommandAttempts / duración nativa`; presupuesto
y buffer usan el intervalo nominal de esa ventana. No se suman `numcmds`, backups,
paquetes ni otras etapas. Los umbrales se conservan como configuración inicial,
pero su calibración y coexistencia con otros filtros requieren pruebas SRCDS.
Una invocación observada sigue sin acreditar ejecución original o simulación física.
`sm_speedwatch_status` solo muestra el último snapshot leído por el timer: no lo
consume ni altera el cursor del detector. `executed_signal=0 physical_signal=0`
expone los límites de esta señal, incluso con todas las capacidades disponibles.

Los hooks no hacen disco, red, formateo ni forwards SourcePawn. No asignan memoria
para cada comando; cada participante posee solo acumuladores y un snapshot, sin
capturas detalladas ni colas de tamaño dictado por el cliente. La baja de un
participante puede liberar su registro. El límite de metadatos 65535 protege el
agregado; no bloquea ni cambia la decisión del juego. `GetStatus(1/2)` informa
memoria del servicio/registros, no todo SourceMod ni las reservas de SourceHook.
La caché diagnóstica de SourcePawn mantiene una muestra pequeña por slot.
La API pública de alertas y episodios sigue exportada. Se retiró el callback
SourcePawn por comando; no hay ahorro de CPU demostrado sin medición comparable.

## Instalación y rollback

Usar el ZIP de la plataforma x86 correcta: SMX, extensión `.so` o `.dll`, fuentes
permitidas, ambos includes públicos, traducciones, licencia, logs y build-info.
Requiere SourceMod/Metamod compatibles con L4D2 y sus gamedata `sdktools.games`.
No se distribuyen SDKs ni librerías del juego. Se reutiliza el offset por nombre
de SDKTools; no se añade un archivo de gamedata con offsets sin evidencia propia.
Mantener las gamedata oficiales al actualizar el juego y volver a validar los hooks.

Para rollback de esta migración, restaurar juntos SMX y extensión de una release
anterior validada. Quitar solo la extensión suspende el detector 0.10.0 y no activa
ningún backend alternativo. Confirmar status, gracia y API antes de volver a usar
las alertas. La instalación, recarga y rollback de 0.10.0 requieren validación SRCDS.

## Diagnóstico de la evaluación

El log añade motivos explícitos (y máscara), sesión/evaluación/epoch e identidad
de ventana para enlazar lectura, evaluación, sospecha y alerta. La lectura ausente
se registra como `sample_unavailable`, sin inventar una causa que la API no expone.
El contexto inicial y el contrato de correlación se describen en
[logs y debug](../logging/README.md#contexto-y-correlación-del-candidato-0100).

## Lectura, evaluación e identidad en 0.12.0

La versión 2 mantiene 48 celdas y exige recompilar los consumidores nativos.
Una solicitud v1 se rechaza antes de tocar el destino. No cambia el include
público `l4d2_speedwatch.inc` que consume BanSystem Demo.

`ReadNativeObservation` copia sin efectos secundarios; `EvaluateNativeWindow`
valida y avanza el cursor exclusivo de la regla; status y la API pública leen
la caché. Los campos `CoreCell_*` y `SampleCell` documentan la serialización.
`NativeCadenceWindow` entrega a la política comandos/duración/intervalo tipados.
Solo se guarda una observación wire por participante y una evaluación distinta;
no se mantiene otra copia del recolector ni historial de comandos.

La identidad compuesta contiene instancia, conexión userid/serial, generación de
participante, epoch de configuración/observación y sample_id low/high. Un cambio
interrumpe continuidad; la primera ventana solo prepara el cursor. La instancia
se genera con reloj monotónico del proceso y desempate entre servicios; no es
UUID de incidente, identidad global entre hosts ni tiempo Unix.

Los estados de regla distinguen ausente, publicado, obsoleto, interrumpido,
capacidad ausente, inválido, primera ventana y duplicado. Datos ausentes jamás
son cero actividad. La retención es 2 s; ventanas 0.5–2 s y lease 2.5 s pertenecen
al servicio y tienen constantes explícitas. El validador del consumidor repite
los límites como defensa del contrato; no construye otra ventana.

Disponibilidad por grupo: bloques, intentos y equipo. Calidad de reloj/ticks o
identidad afecta todos los grupos; metadatos inválidos pertenecen a bloques;
saturación/indisponibilidad puede afectar bloques e intentos y se trata de forma
conservadora. Las máscaras `SPEEDWATCH_QUALITY_*` nombran esas dependencias.
La regla de cadencia necesita intentos, equipo y bloques para excluir ignore/paused;
no necesita señal física ni pasos ejecutados. Mala calidad de un grupo requerido
o bits desconocidos interrumpen; no se sustituye un contador por otro. Perder o
recuperar capacidades reinicia la observación, también a nivel de participante.

`GetStatus(3)` consulta propiedad sin reclamarla: 0 libre, 1 consumidor actual,
2 otro plugin. SpeedWatch suspende la regla y evita Pulse/SetParticipant si el
controlador pertenece a otro consumidor. Su liberación exige epoch nuevo y
ventana de preparación; nunca transforma el hueco en recuperación.
