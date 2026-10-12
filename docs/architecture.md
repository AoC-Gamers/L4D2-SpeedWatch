# Arquitectura y alcance del detector

[Índice de documentación](index.md) · [README](../README.md)

## Alcance del detector

La señal es el número de invocaciones de `OnPlayerRunCmdPre` por tiempo real,
comparado con el tickrate nominal del servidor. Se cuentan las invocaciones,
sin usar `cmdnum` ni `tickcount` enviados por el cliente como reloj o como
presupuesto. El forward se ejecuta antes de otros filtros de comandos: una
alerta no acredita que todos esos comandos terminaran simulando movimiento.

Este enfoque apunta al speedhack basado en exceso de comandos. No detecta por
sí solo toda modificación de velocidad, aceleración, teleport o exploits que
conserven una cadencia normal. Tampoco puede recuperar comandos que el motor
haya descartado antes del callback.

Referencia revisada:
[SMAC Anti-Speedhack](https://github.com/srcdslab/sm-plugin-SMAC/blob/master/addons/sourcemod/scripting/smac_speedhack.sp).
Ese módulo ya tiene una ruta simple, un presupuesto de dos segundos de ticks,
una evaluación cada 0.1 s y bloqueo cuando agota el presupuesto. No hay una
medición que atribuya el consumo de CPU de una instalación de SMAC a este módulo.
SpeedWatch cambia tanto el coste como el comportamiento; no es equivalente
al mecanismo preventivo de SMAC.

## Diseño

El plugin se organiza en un entrypoint y tres módulos privados bajo
`addons/sourcemod/scripting/`:

| Archivo | Responsabilidad |
| --- | --- |
| `l4d2_speedwatch.sp` | Metadatos, ConVars, runtime general, ciclo de vida, eventos y comando de estado |
| `l4d2_speedwatch/logging.sp` | Logger, archivo, categorías debug y registros obligatorios |
| `l4d2_speedwatch/integrations.sp` | Forwards y reconciliación de pause, readyup y Left4DHooks |
| `l4d2_speedwatch/detector.sp` | Conteo, evaluación, resets, muestras, episodios, alertas e implementación de la API |

El entrypoint declara las ConVars y el único runtime general antes de incluir
los módulos. Incluye logging primero, después detector y finalmente integraciones;
así el logger y los datos del detector están declarados antes de los callbacks
del principal. Cada módulo conserva su estado específico. Los tres se compilan
dentro de `l4d2_speedwatch.smx`; no son plugins independientes. El contrato público
para consumidores sigue en `include/l4d2_speedwatch.inc`.

`AskPluginLoad2` comprueba el motor L4D2 antes de registrar la API; en otro motor
rechaza la carga con `APLRes_Failure` y un mensaje de error. Guarda `late` una sola
vez en `g_Runtime.lateLoad`. `PluginRuntimeState` reúne ese contexto y el estado
del mapa, de la observación y de las bibliotecas `pause`, `readyup` y `left4dhooks`;
mantiene `pauseNeedsSync`, `readyUpNeedsSync` y `modeNeedsSync` independientes.
`OnPluginStart` recorre los clientes existentes
únicamente si esa carga es tardía; en carga normal, `OnClientPutInServer`
inicializa cada slot al entrar.

Los handlers de forwards de los proveedores procesan la transición sin volver a
comprobar la biblioteca: la notificación proviene del proveedor activo. Las
llamadas a natives opcionales sí se protegen con la presencia de su biblioteca.

- `OnPlayerRunCmdPre`: comprueba mapa/observación/pausa/readyup/sincronización y elegibilidad en memoria,
  e incrementa el contador entero de comandos. Para humanos consulta directamente
  la ConVar de debug y, si está activo, la máscara de flags. Sin traza habilitada
  no obtiene userid ni consulta propiedades de entidades, formatea texto o envía chat.
- Un timer compartido de 1 s; recorre los slots y consulta estado de los humanos.
- Solo humanos vivos en equipos 2 o 3. También puede observar infectados fantasma
  si el motor los considera vivos. Bots y espectadores no se evalúan.
- Exceso acumulado por cliente, limitado a dos veces el buffer. Se reduce cuando
  llegan menos comandos de los permitidos. Una ventana sin exceso corta la racha.
- Tres muestras consecutivas por encima del buffer antes de alertar.
- Gracia tras conexión, primera muestra vivo, muerte, cambio de equipo, inicio
  de ronda, cambio de mapa, cambios del detector o muestra global inválida.
- Cooldown por conexión; sobrevive a resets de ronda/configuración/retrasos.
- El timer persiste entre mapas; no se crean timers por jugador. SourceMod lo
  libera al descargar el plugin.

La comprobación global compara ticks avanzados con tiempo real. Descarta la
muestra si el intervalo real del timer sale de 0.5–2 s, si los ticks avanzan
fuera del 80–120% de lo esperado, cambia el tickrate, no hay simulación, o
`host_timescale` difiere de 1. Se borra el historial y vuelve a aplicar gracia.
Es una protección conservadora: puede suspender el detector en servidores con
bajo rendimiento. No distingue automáticamente todos los problemas de red y
no promete eliminar falsos positivos. No replica el filtro de latencia de SMAC.

La biblioteca opcional `readyup` excluye su fase de preparación y cuenta regresiva.
Sin ese proveedor, la observación usa las comprobaciones generales descritas aquí.
`round_start` reabre la observación, descarta historial y pide sincronizar readyup; no define por sí solo
una partida, mitad ni estado live. El plugin permite guardar logs de diagnóstico
en su archivo propio. Cada alerta también escribe una línea en la consola del servidor.

## Mapa y validez de observación

`g_Runtime` mantiene tres estados con responsabilidades distintas:

- `mapLoaded`: se activa únicamente en `OnMapStart` y se retira en `OnMapEnd`.
  `OnPluginStart` no supone que ya exista un mapa. SourceMod también entrega
  `OnMapStart` a una carga tardía si el mapa está disponible.
- `observationEnded`: suspende la observación al recibir `round_end`,
  `map_transition`, `mission_lost`, `finale_win`, `versus_match_finished`,
  `scavenge_round_halftime`, `scavenge_round_finished` o `scavenge_match_finished`.
  Con Left4DHooks y modo Versus confirmado, el cierre de mitad usa
  `L4D2_OnEndVersusModeRound_Post` y se ignora `round_end`.
  El mapa puede seguir cargado durante ese cierre.
- `sampleValid`: indica si la última evaluación cumplió las condiciones de
  tiempo real, avance de ticks, tickrate, timescale y detector habilitado.
  Cada reinicio del historial la invalida.

Los eventos de fin descartan inmediatamente comandos, exceso, rachas y muestras
de API. Suspenden también la traza por comando. `round_start` y
`scavenge_round_start` reabren la observación con gracia y nueva sincronización de
readyup; las exclusiones de ambos proveedores siguen vigentes. Reanudar pausa,
salir de readyup, cambiar ConVars o ejecutar cfg no elimina un cierre lógico.
Un `OnMapStart` posterior a una señal de fin tampoco lo elimina. `OnMapEnd`
invalida las muestras como respaldo y limpia el cierre anterior para el próximo
mapa, que sigue bloqueado hasta su `OnMapStart`.

Estos eventos delimitan ventanas conservadoras del detector; SpeedWatch no
construye un historial de rondas ni declara el estado competitivo live. Si se
carga tarde, no recupera eventos de fin anteriores a su carga: comienza con las
comprobaciones de simulación, la sincronización de proveedores y la gracia.
`sm_speedwatch_status` muestra `map_loaded`, `observation_ended` y `valid_sample`.
El debug de lifecycle registra `observation_end` con el evento que lo produjo.

## Regla de sospecha

Para una muestra válida de duración real `dt`, intervalo de tick `T` y `C`
comandos observados:

```text
esperado = dt / T
permitido = esperado × sm_speedwatch_rate
buffer = sm_speedwatch_burst / T
exceso = clamp(exceso_anterior + C − permitido, 0, 2 × buffer)
racha = racha + 1 si exceso ≥ buffer y C > permitido; en otro caso 0
alerta si racha ≥ sm_speedwatch_samples y terminó el cooldown
```

Los defaults permiten 1.10 veces el tickrate y absorben dos segundos de comandos
nominales excedentes. No se acumula crédito ilimitado por quedarse quieto.
A 30 ticks/s: permitido ≈33 comandos/s, buffer ≈60 comandos. A 100 ticks/s:
permitido ≈110 comandos/s, buffer ≈200 comandos. El estado en gracia muestra
cadencia, pero no acumula exceso.

Con tráfico ideal constante a 1.5 veces el tickrate, el cálculo tarda unos 7–8 s
de muestras válidas después de la gracia en alertar. A 1.2 veces, unos 22–23 s.
Son estimaciones matemáticas, no resultados de SRCDS. Un exceso de hasta el 10%
queda dentro del margen por diseño. Ráfagas intermitentes pueden quedar bajo
los umbrales; las modificaciones que mantengan la cadencia normal quedan fuera
del alcance de esta señal.

## Coste esperado

Ambos plugins conservan un callback por comando: no se elimina ese coste.
`Pre` es de solo lectura y SourceMod no necesita copiar modificaciones de vuelta
desde este forward, aunque sigue preparando sus argumentos. El timer pasa de
10 a 1 evaluación nominal por segundo. Las consultas de estado pasan a esa
evaluación, y SpeedWatch omite consultas periódicas de latencia.

Estas diferencias justifican medir una reducción, no afirmar un porcentaje.
Si otros plugins usan `OnPlayerRunCmd`, sus callbacks y costes siguen presentes.
Deshabilitar la ConVar detiene el conteo, pero el forward continúa registrado.
Para medir el coste completo del hook hay que descargar el plugin.

Fuentes de API e implementación:
[forward de SourceMod](https://github.com/alliedmodders/sourcemod/blob/master/plugins/include/sdktools_hooks.inc)
y [SDKTools hooks.cpp](https://github.com/alliedmodders/sourcemod/blob/master/extensions/sdktools/hooks.cpp).

El contrato de episodios y recuperación se describe en [grabación](recording.md).
Las dependencias se detallan en [integraciones opcionales](integrations.md).
