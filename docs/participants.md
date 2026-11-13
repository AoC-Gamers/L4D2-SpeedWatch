# Participantes y aforos reducidos

[Índice](index.md) · [Arquitectura](architecture.md) · [Validación general](testing.md)

## Alcance de este cambio

Esta mejora mantiene el detector de cadencia de 0.8.0 y unifica la elegibilidad
utilizada por la evaluación periódica y la consulta pública. No implementa todavía
un detector físico de movimiento ni pretende identificar una DLL determinada.

Un candidato debe ser un humano conectado, dentro del juego, vivo y miembro del
equipo 2 (supervivientes) o 3 (infectados). La condición se comprueba en el timer
y al consultar la API. La ruta por comando utiliza la elegibilidad almacenada en
`g_bMonitor`, que se invalida mediante el ciclo de vida existente.

No se exige un mínimo de participantes ni equipos completos. El presupuesto de
comandos se calcula por jugador a partir del tiempo de la muestra y del intervalo
de tick; no se divide ni multiplica por la cantidad de jugadores conectados.
Las exclusiones globales de pausa, readyup, cierre de observación y simulación
irregular siguen aplicándose, incluso con un único participante.

| Situación | Política de este cambio |
| --- | --- |
| 1v1, 2v2, 3v3, 4v4 | Evaluar individualmente los humanos elegibles presentes |
| Equipos temporalmente incompletos o desiguales | No esperar a que se complete un aforo |
| Práctica con un humano | No bloquear por población; respetar las demás exclusiones |
| Cero humanos elegibles | No contar ni evaluar muestras individuales |
| Más de ocho humanos en equipos jugables | No truncar silenciosamente la observación a ocho |
| Participante en un índice superior a ocho | Usar su índice real, hasta `MaxClients` |
| Espectador, bot o humano muerto no monitorizado | No contar comandos ni generar traza por comando |
| Administrador espectando | Mantener la recepción de alertas según los permisos existentes |

El número de conexiones presentes no identifica el formato configurado. Dos
jugadores conectados pueden ser una partida 1v1 o una partida 4v4 incompleta.
Este cambio no intenta inferir ni anunciar un formato a partir de ese número.

## Espectadores y ciclo de vida

`OnPlayerRunCmdPre` abandona antes de consultar debug o formatear texto si el
cliente no está monitorizado. La traza `DEBUG_COMMANDS` ya no registra comandos
con `tracking=0`; las muestras en gracia pueden seguir teniendo `tracking=1`.

En una evaluación válida, un humano no elegible sin datos de observación no
necesita otro `ResetClient` cada segundo. Si todavía tiene seguimiento, muestra,
episodio o contadores, se conserva la limpieza habitual. Al volver a ser elegible,
la rama de inicio de seguimiento aplica de nuevo la gracia completa.

Los resets globales, la cola de transiciones, los cooldowns por conexión y los
handlers de muerte, equipo y desconexión no cambian. El paso a espectador no debe
producir `Recovered`: se conserva la interrupción del episodio con su identidad
original. La API y su estructura pública mantienen el tamaño y las firmas.

El conteo de comandos de infectados fantasma conserva la política de 0.8.0: puede
observarlos si el motor los considera vivos. Su exclusión del análisis físico es
un requisito para una futura capa de movimiento, no una funcionalidad añadida aquí.

## Coste y memoria

Se eliminan consultas de debug y trazas por comando para no monitorizados, y
resets periódicos redundantes durante muestras válidas. No se ha medido un ahorro
de CPU ni de memoria en SRCDS.

Los arrays pequeños indexados por slot se conservan. Por tanto, este cambio no
elimina la reserva estática correspondiente a espectadores ni implementa un pool
compacto de registros analíticos. Tampoco agrega arrays, timers o historiales nuevos.
El recorrido periódico hasta `MaxClients` se conserva como reconciliación segura.

Para una futura capa de contexto más costosa, usar registros solo para los
participantes elegibles, sin asociar la capacidad a ocho índices de cliente. El
crecimiento debe estar acotado por el servidor, manejar altas/bajas y nunca
condicionar la detección a que haya un número exacto de jugadores.

## Validación local y pendiente

`tests/test_participant_policy.py` contiene comprobaciones estructurales y una
prueba de lógica extraída del SourcePawn. Compila únicamente funciones simples en
C++ con dobles de prueba de las APIs. No compila ni ejecuta el plugin SourcePawn.
Se ejecuta mediante:

```sh
python3 -m unittest discover -s tests -p test_participant_policy.py -v
```

Requiere un compilador C++ para cinco casos de lógica; si falta, esos casos se
marcan omitidos y siguen ejecutándose las dos comprobaciones estructurales.
Las funciones de ciclo de vida, alertas, muestras y cola que deben permanecer
intactas se comparan con sus hashes en la revisión base `08f735c`.

La prueba cubre poblaciones de 0, 1, 2, 4, 6, 8 y 12 humanos; índices altos;
bots, espectadores, muertos, desconectados e índices inválidos; ausencia de
consultas de entidades en la ruta por comando; supresión por pausa/readyup y
necesidad de limpiar observación residual.

Integración local validada: producción y ambos consumidores de API compilan con
SourcePawn 1.12.0.7255 sin warnings; las doce pruebas del repositorio pasan,
incluidas las siete comprobaciones de este parche. Se conserva la corrección
previa del respaldo de cierre de Versus durante carga tardía.

Antes de desplegar, falta ejecución en SRCDS. La matriz de runtime debe
incluir cambios espectador/equipo, muerte/respawn, reemplazo de bots, reutilización
de slots, cambios de aforo, rondas y mapas, carga tardía, forwards reentrantes y
recepción de alertas por un administrador espectador. Las pruebas aisladas no
certifican esas transiciones, el rendimiento ni la tasa de falsos positivos.

## Contexto físico pendiente

La futura capa deberá diferenciar velocidad horizontal de la entidad,
desplazamiento por tiempo real y cadencia de comandos. Debe registrar clase,
suelo/aire, salud temporal, adrenalina, habilidades, movimiento forzado y política
de bhop efectiva. Una velocidad de carrera de referencia no es un límite físico
universal, ni el aforo del modo determina sus valores.

No se añaden en este parche límites de 220/250/300 unidades/s ni nuevas alertas
físicas: requieren validar el estado y las modificaciones efectivas del servidor.

## Registros del núcleo nativo

La extensión de 0.9.0 añade registros solo para participantes elegibles, con userid/serial/generación, sin mínimo de aforo. No crea historial pesado de espectadores. Su grupo de contexto físico no está disponible; el contrato temporal de infectados fantasma permanece.

Ver [contrato del núcleo](native-core/index.md), [evidencia ABI](native-core/evidence.md) y [validación](native-core/validation.md).
