# Criterios de configuración del detector nativo

[Índice](index.md) · [Valores y límites](installation.md) · [Migración](migration-native.md)

La tabla canónica de ConVars y sus valores está en instalación. `rate`, `burst`
y `samples` parametrizan cadencia de **intentos**, no velocidad física ni pasos
simulados. La migración conserva sus valores y la protección ante ráfagas; no
acredita una recalibración. `dropped_packets` no descarta por sí solo una ventana.

`grace` se aplica al admitir/reiniciar observación; no acumula sospecha.
`recovery_time` exige cadencia normal válida y consecutiva, nunca ausencia de datos.
`cooldown` solo limita avisos; no cambia Active ni los marcadores cada 30 segundos
de exceso confirmado. Los resets conservan cooldown salvo nueva conexión.

`sm_speedwatch_public=0` sigue siendo el valor privado predeterminado; el modo
público continúa como opción explícita. `debug_flags` usa 1/2/4/8 y reserva el
antiguo bit 16. Retirar `sm_speedwatch_core_compare` de cfg; no hay fallback ni
ConVar para cambiar al recolector anterior. Pausa/readyup, procesamiento y
`host_timescale` conservan sus exclusiones. Ver [logs](logging.md).
