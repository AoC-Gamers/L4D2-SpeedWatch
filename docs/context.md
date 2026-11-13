# Contexto de L4D2 y partidas de tamaño variable

[Índice](index.md) · [Arquitectura](architecture.md) · [Validación](testing.md)

## Alcance de esta entrega en develop

El detector sigue observando cadencia de comandos. Este cambio incorpora contexto
**diagnóstico** a los logs, no un segundo detector de velocidad física. No cambia
los umbrales, el presupuesto temporal, el cooldown ni la API pública 0.8.0.
No identifica una DLL y no bloquea, expulsa ni sanciona a jugadores.

`context.sp` es un módulo privado incluido por `detector.sp`; ambos se compilan
en el mismo SMX. No requiere otro plugin, gamedata adicional ni una extensión.

## Participantes: no exigir ocho jugadores

Solo se evalúan humanos vivos en equipo 2 (supervivientes) o 3 (infectados),
con las exclusiones globales habituales. No existe mínimo, exigencia de equipos
completos, simetría ni máximo analítico de ocho. La misma selección sirve para
1v1, 2v2, 3v3, 4v4, equipos incompletos, otros tamaños y modos con humanos solo
en supervivientes. Esto no certifica todas las reglas de cada mutación.

Se recorren índices `1..MaxClients`: un jugador válido puede estar en el slot 19
aunque solo haya dos participantes. `survivor_limit` y `z_max_player_zombies`
se registran como configuración, pero **no limitan** el recorrido ni se usan
para descartar a un humano. Un modo modificado puede usar otros mecanismos.

Los espectadores no acumulan comandos ni generan traza por comando. Pasar a
espectador mantiene el reinicio/interrupción existente por cambio de equipo.
Los administradores espectadores siguen pudiendo recibir alertas.

`humans_survivor` y `humans_infected` cuentan integrantes humanos presentes en
esos equipos, incluidos muertos/fantasmas, no solo sujetos evaluables. No son
la capacidad del servidor ni la prueba de que se juega una modalidad concreta.
Los infectados fantasma conservan el comportamiento del detector de cadencia
previo, pero su contexto lleva `ghost=1`; su velocidad no debe compararse con
la de un infectado materializado.

## Captura y coste

Se conserva el temporizador compartido de un segundo. El contexto se captura
solo cuando se necesita escribir una muestra de debug (`DEBUG_SAMPLES`) o una
alerta fuera de cooldown y el log está disponible. En operación ordinaria sin
alertas ni debug no se consultan las propiedades físicas para este contexto.

No hay un nuevo callback por comando, temporizador, historial de posiciones,
lista de comandos ni array de contextos por slot. El perfil se captura una vez
por evaluación que lo necesite; la fotografía del jugador es una estructura
local que se toma antes de notificar a consumidores externos. Se registra esa
copia, no el estado que un consumidor haya modificado después.

Los arrays existentes de cadencia por slot permanecen. No se afirma una
reducción medida de memoria total o CPU. La cola de transiciones ahora utiliza
un cursor y se limpia al terminar, evitando `Erase(0)` repetido; conserva FIFO,
la protección de reentrancia y los eventos añadidos durante la notificación.

## Interpretación del log

Las alertas añaden una línea `[context] event=movement_context` aunque debug esté
apagado, si el archivo está disponible. Con debug de muestras se escribe también
para cada muestra publicada, incluidas las de gracia. Se enlaza con la muestra
o alerta por `slot`, `userid` y tiempo del motor. Los valores desconocidos o no
aplicables se representan con `-1`, no se sustituyen por valores vanilla.

| Campo | Significado |
| --- | --- |
| `schema=1`, `scope=sample_end` | Formato y alcance: fotografía al evaluar, no un agregado de toda la ventana. |
| `source=sample/alert` | Diagnóstico periódico o copia que acompaña una alerta. |
| `time`, `server_tick` | Tiempo de evaluación y tick del servidor; `time` no es una fecha Unix. |
| `mode` | Valor observado de `mp_gamemode`, o `unknown`. No identifica ZoneMod ni su versión. |
| `humans_survivor`, `humans_infected` | Población humana por equipo al capturar el perfil. |
| `survivor_limit`, `infected_limit` | Valores observados de las ConVars correspondientes, o `-1`. |
| `team`, `class` | Equipo y clase de infectado; `class=0` para supervivientes. |
| `ground`, `duck`, `water`, `movetype` | Estado instantáneo del suelo/agachado, nivel de agua y tipo de movimiento. |
| `ghost`, `incap`, `hanging`, `adrenaline` | Estados observados; `-1` si la propiedad falta o no aplica. |
| `pinned` | Propietario de lengua, pounce, Jockey, transporte o pummel de Charger. No cubre toda fuerza externa. |
| `health`, `health_buffer_raw` | Salud permanente y buffer temporal bruto; el segundo no es salud temporal restante. |
| `speed2d` | Magnitud horizontal de `m_vecAbsVelocity`, no el `vel` deseado de `OnPlayerRunCmdPre`. |
| `maxspeed_prop` | Valor observado de `m_flMaxspeed`. No equivale a un máximo físico universal ni garantiza el resultado final de todos los plugins. |
| `bhop_config` | Configuración declarada: `-1` desconocida, `0` anti-bhop desactivado, `1` clase restringida, `2` clase exenta. |

Las clases L4D2 son Smoker=1, Boomer=2, Hunter=3, Spitter=4, Jockey=5,
Charger=6 y Tank=8. La máscara de `bhop_except_si_flags` usa bits 0..5 para
las primeras seis clases y bit 6 para Tank. Witch=7 no se interpreta como Tank.

La existencia de las ConVars de anti-bhop **no garantiza que el plugin siga
cargado ni que la limitación se haya ejecutado**. Por eso el campo se llama
`bhop_config`, no `bhop_enforced`. No prueba que el jugador esté haciendo bhop.

## Lo que esta fotografía no demuestra

No mide picos, duración en aire, aterrizajes ni rachas de saltos. Un muestreo de
un segundo puede omitir una habilidad completa. No reconstruye desplazamiento
por segundo real ni diferencia automáticamente pounce, leap, charge, empujones,
plataformas, triggers o teletransportes. `pinned=0` no significa ausencia de
fuerzas externas. El contexto no puede invalidar una sospecha de cadencia ni
crear una acusación por superar `maxspeed_prop`.

No se han incorporado límites rígidos de 220/250/300 unidades por segundo ni
valores universales de bhop. La futura instrumentación temporal debe distinguir
recepción/ejecución/simulación y documentar las reglas efectivas del servidor,
las transiciones y la calidad de observación antes de generar nuevas alertas.

## Validación

`make test-ci` descubre `tests/test_context_contract.py`. Son comprobaciones de
contrato del código y modelos pequeños, **no ejecución de SourceMod ni pruebas
de detección en SRCDS**. Cubren selección con poblaciones variables, índices altos,
exclusión de espectadores, captura previa a forwards, datos desconocidos, señal
inalterada, configuración de bhop y orden FIFO con inserciones reentrantes.

La compilación real se realiza mediante `make build-smx` o GitHub Actions.
No sustituye esta matriz de runtime pendiente:

- 1v1, 2v2, 3v3, 4v4, equipos incompletos y servidores sin participantes; incluir
  bots, espectadores y humanos con índices superiores a ocho.
- Equipo/espectador, desconexión, reutilización de slot, muerte, respawn, cambios
  de control, pausa, readyup y cambio de mapa; no heredar datos entre conexiones.
- `debug=0`: ausencia de capturas periódicas y contexto en alertas; debug de
  muestras y de comandos por separado; error del logger sin romper el detector.
- Superviviente normal/herido/agachado, adrenalina, agua, infectado fantasma,
  todas las clases, salto y desplazamientos forzados; revisar propiedades ausentes.
- Anti-bhop ausente, cargado, desactivado y descargado con ConVars persistentes;
  no confundir configuración con ejecución efectiva.
- Un consumidor que cambia estado desde `Active`: interrupción coherente y sin
  alerta ni contexto atribuidos a una conexión nueva; varios episodios simultáneos.

## Referencias de implementación

- [SourceMod: OnPlayerRunCmdPre y movimiento deseado](https://github.com/alliedmodders/sourcemod/blob/master/plugins/include/sdktools_hooks.inc).
- [SourceMod: flags y tipos de movimiento](https://github.com/alliedmodders/sourcemod/blob/master/plugins/include/entity_prop_stocks.inc).
- [Simple Anti-Bunnyhop: ConVars, máscara por clase y corrección al aterrizar](https://github.com/SirPlease/L4D2-Competitive-Rework/blob/master/addons/sourcemod/scripting/l4d2_nobhaps.sp).

Estas referencias explican campos e interfaces. No acreditan la configuración
instalada, el comportamiento de una DLL ni la eficacia de SpeedWatch en partida.
