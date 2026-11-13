# Evidencia, tipos y límites ABI

Base SpeedWatch: `9ce41ca7a878ec87bf81d30449c4b39e1bf55582` (`develop`).
Referencia Custom-Fakelag: `b871f52dc5903308c73cc08bc8348c793844729d`, checkout
local leído sin modificar. No estaba disponible el informe externo de protección;
no se atribuyen a ese informe mediciones ni resultados de esta implementación.

## Fuentes

- [HL2SDK L4D2, eiface.h](https://github.com/alliedmodders/hl2sdk/blob/2a31cd007b2d7d2f964dc093eedcf7a812cf9dd6/public/eiface.h)
- [SDKTools hooks.cpp](https://github.com/alliedmodders/sourcemod/blob/3f7460671f7adc4a3c6791a47d21ba3e7b5fba91/extensions/sdktools/hooks.cpp)
- [SourceHook](https://wiki.alliedmods.net/SourceHook_Development)
- [CServerGameClients en Ghidra exportado](https://binaries.l4d2node.org/b/server_srv.so/c/CServerGameClients)
- [CBasePlayer::PlayerRunCommand exportado](https://binaries.l4d2node.org/b/server_srv.so/f/0x007a7850)
- [CBasePlayer::DetermineSimulationTicks exportado](https://binaries.l4d2node.org/b/server_srv.so/f/0x007ad610)
- [DT_TerrorPlayer](https://netprops.l4d2node.org/class/DT_TerrorPlayer)

Los commits de dependencias están fijados en `dependencies.lock.json` y el paquete
SourcePawn está fijado por URL y SHA256 en `sourcepawn-package.lock.json`. Cada
artefacto registra resoluciones, compilador, SHA de proyecto e inputs de build.
La decompilación pública corresponde a un módulo Linux; sus direcciones son
referencias de navegación, no offsets o firmas que se instalen en la extensión.
El sitio no ofrece aquí una certificación de ABI del servidor del usuario.

## Correspondencia motor → adaptador → telemetría

| Motor | Tipo/adaptador local | Campos / unidad | Resolución y evidencia |
| --- | --- | --- | --- |
| IServerGameClients::ProcessUsercmds | Hook de interfaz de CommandHooks.cpp | numcmds/totalcmds/dropped_packets, ignore/paused, último instante/tick | Prototipo exacto en eiface.h; SourceHook; Linux/Windows x86 como objetivos de build |
| bf_read | Puntero prestado del SDK | Ninguno | Opaque: sin lectura, copia, avance ni layout supuesto |
| PlayerRunCommand | Manual hook con CUserCmd*, IMoveHelper* | runCommandAttempts, último ID/instante/tick | Key `PlayerRunCmd` de sdktools.games; misma firma que SDKTools; no lectura de payload |
| CUserCmd | Tipo SDK en AbiChecks.cpp; declaración opaca en hook | Ninguno | Comprobación de tipado/alineación natural x86; sin offsetof, sizeof fijo ni copia |
| command_number / tick_count | No se leen | No disponibles | No se usan para deduplicar o como reloj confiable |
| CCommandContext | Sin vista implementada | No disponible | Sin layout validado: no se lee la cola ni se suma su contenido |
| CBasePlayer / CTerrorPlayer | Puntero opaco CBaseEntity + IPlayerInfo | Equipo de la ventana | Interfaces públicas, sin herencia/vtable reconstruida |
| m_nTickBase | Sin adaptador | No disponible | Sin lecturas; no se confunde corrección de tickbase con ejecución |
| CGlobalVars::tickcount / interval_per_tick | Globals obtenidos de Metamod | Ticks efectivos / segundos nominales por tick | SDK público, separados del reloj steady_clock |
| IGamePlayer | Identity propio | userid, serial y AccountID validado | SourceMod; nueva conexión no hereda registros |
| DT_TerrorPlayer y propiedades físicas | Sin lecturas implementadas | Grupo físico no disponible | Netprops sirve de inventario; bits SendTable no prueban almacenamiento C++ |

El tamaño de un `CUserCmd` de una decompilación concreta no se fija en el código.
Las comprobaciones de SDK compilan con flags x86 y validan la firma de interfaz,
los anchos escalares y que CUserCmd sea polimórfico. No validan contra el binario
instalado en SRCDS. Tampoco se instancian ni liberan objetos del motor.

## Plataformas y capacidades

| Objetivo | Estado de implementación | Verificación local |
| --- | --- | --- |
| Linux x86 | Bloques, intentos y equipo; degradación sin offset RunCommand | Build AMBuild y ABI SDK x86; ELF/exports; pruebas de servicio y SourceHook |
| Windows x86 | Mismo código con interfaz SDK y gamedata oficial propia de plataforma | Targets y CI preparados; build MSVC y PE real pendientes en host Windows |
| x64 | No soportado | static_assert rechaza sizeof(void*) distinto de 4 |
| Internals avanzados | Sin capacidad anunciada | Pendientes ProcessUsercmds interno, DetermineSimulationTicks, AdjustPlayerTimeBase y PhysicsSimulate |

Un pre hook cuenta una invocación observada aunque otro hook la suprima. La prueba
con SourceHook real y objeto sintético muestra post tras SUPERCEDE y reentrancia;
no prueba coexistencia dentro de SRCDS. No se anuncia una capacidad de ejecución
original, bloqueo demostrado por llamada ni pasos confirmados de simulación.
El contador propio de invocaciones diferencia llamadas distintas, incluso si sus
comandos tienen números iguales. No se añade otro hook que cuente la misma llamada.

## Convenciones adaptadas

| Custom-Fakelag | Adaptación SpeedWatch | Motivo |
| --- | --- | --- |
| Make + AMBuild/configure/AMBuilder/PackageScript | Misma entrada y mecanismo nativo | Evitar un segundo sistema de build |
| Servicio + puente de API | ObservationService + SampleCodec/NativeBridge | Probar implementación real sin SDK ni motor |
| Separación SDK/runtime | ABI pública y punteros opacos; sin vistas internas | No hay evidencia suficiente para leer internals |
| Dependencias separadas por plataforma | .deps/smx, .deps/exts-linux, .deps/exts-windows, commits fijados | Reproducibilidad y cachés independientes |
| Empaquetado plugin/extensión | SMX compartido y ZIP por plataforma, allowlist y hashes | Nunca exigir .so y .dll juntos; no mezclar salidas |
| Perfiles y alteración de tráfico | No trasladados | Dominio exclusivamente observacional |

`AMBuildScript` y `configure.py` se adaptan del template empleado por Custom-Fakelag;
se conserva la licencia GPL del repositorio y se registra esta procedencia. No se
copiaron sus estructuras de paquetes, detours de tráfico ni reglas de simulación.
