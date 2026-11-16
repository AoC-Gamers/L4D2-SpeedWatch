# Validación del núcleo nativo

La separación 0.12.0 incorpora API nativa v2, identidad de instancia, estado de
obsolescencia y módulos nuevos. Los checkpoints de versiones anteriores más
abajo son históricos: no validan automáticamente este conjunto ni su runtime.
La aceptación actual pendiente está en [migración](../migration-native.md).

## Capas de evidencia

1. Pruebas unitarias compilan `ObservationService.cpp` y `SampleCodec.cpp` reales:
   metadatos nuevos/backups/pérdidas, contadores independientes, cero crédito por
   recepción, límites, overflow, identidad/slots altos, aforos 0–100, epochs,
   intervalos, pausas, hitches, reloj regresivo, ausencia/obsolescencia y buffers.
2. Prueba SourceHook enlaza su implementación fijada y usa un objeto sintético:
   original, filtro semejante al de SDKTools, SUPERCEDE, post, reentrancia y teardown.
   No valida el objeto del juego ni la coexistencia con SDKTools cargado en SRCDS.
3. `AbiChecks.cpp` compila la firma de eiface.h y tipos SDK con flags x86. El
   binario se valida como ELF32 x86 / PE32 x86 y con GetSMExtAPI/CreateInterface_MMS.
4. Pruebas Python ejercitan builds y empaquetados con fixtures explícitos: sin SDK,
   faltantes/duplicados, binario vacío, arquitectura/exports equivocados, hashes
   obsoletos, documentación no autorizada y separación de árboles por plataforma.
5. Consumidores antiguos y diagnóstico nativo compilan con `spcomp -E`. El test
   nuevo consulta dos veces y comprueba salida no destructiva y buffer mayor.
   Versiones/longitudes inválidas se ejercitan en el codec; errores de natives VM
   reales siguen en la matriz SRCDS.

Comandos reproducibles en Linux con multilib instalado:

```sh
make deps-smx deps-exts-linux
make build-smx build-api-test build-exts-linux
make test-exts-linux test-ci
python3 scripts/run-native-tests.py --platform linux --sanitize
make package-smx package-exts-linux release-linux validate-artifact
actionlint .github/workflows/sourcemod-build.yml
git diff --check
```

Los sanitizadores se ejecutan sobre el núcleo aislado en arquitectura del host
(x64 localmente), no sobre el SDK ni como prueba de ABI x86. La prueba ordinaria
usa `-m32`; no confundir ambas evidencias. No hay captura detallada implementada
que pueda desbordar un historial: solo registros acotados y agregados saturantes.

En Windows: abrir terminal x86 de MSVC (CI inicializa `vcvarsall.bat x86`
mediante `scripts/setup-msvc.py`), Python 3.12 y make;
`make deps-exts-windows build-exts-windows test-exts-windows package-exts-windows
PYTHON=python`. Todos los procesos externos se ejecutan con `check=True`; un fallo
no queda oculto tras el éxito de una instrucción posterior. No se usan wrappers de
PowerShell que ignoren LASTEXITCODE. No se ha ejecutado MSVC en este host Linux.

## Matriz reproducible de SRCDS (pendiente)

No se ha cargado esta extensión en un servidor en esta tarea. Antes de aceptarla:

- Instalar en L4D2 x86 de pruebas y registrar versión/hash del server y engine,
  SourceMod, Metamod y gamedata. Confirmar capacidades reales por participante.
- Sin extensión: confirmar rechazo de carga por dependencia requerida. Con API
  incompatible, confirmar fallo explícito de inicio. Con capacidades insuficientes,
  confirmar detector_ready=0 y registro normal, sin fallback ni falsa recuperación.
- Con extensión: confirmar backend nativo, capacidades, calidad e identidad. Repetir
  1v1/2v2/3v3/4v4, equipos desiguales, práctica con uno, cero, >8 y slots altos.
- Bots, espectadores y admins espectadores: sin registros analíticos para los dos
  primeros; conservar recepción de avisos y permisos del administrador.
- Conectar/desconectar, autorizar tarde, reutilizar slots, morir/respawnear,
  cambiar equipo/control/personaje, takeover de bot, clase, fantasma/materialización.
  Las muestras deben pertenecer al userid/serial correcto y el grupo físico ausente.
- Pausa/readyup/countdown/live, cambio de mapa, reinicio y ambas mitades Versus.
  Preservar `versusEndForwardObserved`, su respaldo y las interrupciones únicas.
- Descargar/recargar core, activar/desactivar detector, quitar offset RunCommand en instalación
  aislada y probar carga parcial fallida. API incompatible y natives no presentes:
  detección suspendida sin fallback, Interrupted único, sin recuperación ficticia ni muestras mezcladas.
- Con varios consumidores, leer repetidamente, omitir varias ventanas, probar
  versiones/longitudes/índices inválidos desde harness aislado. Verificar errores
  nativos y canarios; no incluir el harness en el paquete de producción.
- Coexistencia con SDKTools y plugins de movimiento; hooks que SUPERCEDEan, forwards
  que pausan/desconectan y reentrancia de episodios. No sumar etapas ni alertar dos veces.
- Tráfico limpio, pérdida/jitter/bursts legítimos, hitches, distintos tickrates y
  varios ticks por frame: degradar calidad sin convertir huecos en recuperación.
- Bhop, adrenalina, pounce, charge, Jockey/Smoker, agua, escalera, incapacidad y
  empujones: confirmar que no se anuncian métricas físicas que no están disponibles.
- Medición A/B repetida de baseline, heredado y candidato bajo misma carga:
  CPU/frame times, coste de hooks, memoria e I/O. No ajustar umbrales físicos ni
  prometer ahorro con resultados sintéticos.

La carga tardía no reconstruye el pasado: empieza con epoch nueva, registros
nuevos y gracia. La cadencia nativa requiere calibración con tráfico legítimo; ningún ensayo
requiere un cheat, inyector o alterar el tráfico del juego desde el core.

## Evidencia histórica de la implementación 0.9.0

- Base `9ce41ca`; rama `codex/native-observation-core`; sin publicación o despliegue.
- SourcePawn 1.12.0.7255: producción y tres consumidores de API, `-E`, sin warnings.
- GCC 13.3 / AMBuild fijado: extensión Linux ELF32 x86 y comprobaciones de SDK,
  warnings fatales, exports GetSMExtAPI/CreateInterface_MMS verificados.
- Servicio/codec x86 y cadena SourceHook real con objeto sintético: aprobados.
- ASan/UBSan: servicio/codec en host x64, aprobados; no valida ABI x86 del juego.
- Dieciocho pruebas Python de participantes/pipeline/ELF/PE: aprobadas.
- `actionlint` y `git diff --check`: aprobados.
- ZIP local Linux combinado, validado sin SDK durante la fase de empaquetado:
  `dist/release/l4d2-speedwatch-local-linux.zip`. No es una release publicada.

El host no tenía multilib de desarrollo y sudo no era interactivo. Para validar
sin cambiar el sistema se descargaron y extrajeron paquetes Ubuntu bajo
`.deps/toolchain`: lib32gcc-13-dev/lib32stdc++-13-dev 13.3.0-6ubuntu2~24.04.1,
libc6-dev-i386/libc6-i386 2.39-0ubuntu8.9 y librerías de soporte correspondientes.
Un wrapper local de g++ usa `-m32`, `-B`, rutas de include/library extraídas y
`LD_LIBRARY_PATH` del sysroot. Es una adaptación local ignorada por Git; CI usa
multilib instalado en su runner. Los logs de compilación registran su ruta.
Windows/MSVC, ABI contra el binario externo del juego, SRCDS y rendimiento no
se han ejecutado ni certificado aquí. El workflow remoto está preparado, no ejecutado.

## Migración del detector 0.10.0

Se retira el callback SourcePawn y se conserva solo la señal de intentos del core.
Las pruebas aisladas ejercitan las funciones de producción de admisión de ventanas,
acumulación de deuda, racha, interrupción, recuperación y elegibilidad, con dobles
C++ y adaptación mecánica de sintaxis SP. Cubren identidad/equipo/epoch, capacidades,
primera ventana, duplicados, huecos, generaciones, calidad, metadatos de pérdida, pausa, NaN,
infinitos y contadores no representables. No ejecutan la VM ni certifican gameplay.

La matriz SRCDS anterior se aplica a 0.10.0 y sigue pendiente, incluida la
coexistencia con filtros SUPERCEDE y la calibración de umbrales bajo carga/red real.
La comprobación SSH de 0.9.0 acredita carga de esa versión, no de este candidato.

### Evidencia local del candidato 0.10.0

- `make deps-smx deps-exts-linux` y `make build-smx build-api-test`: correctos;
  SourcePawn 1.12.0.7255, `-E`, producción y tres consumidores sin warnings.
- El host carece de cabeceras multilib. Build y pruebas x86 completados en el
  contenedor local `custom-fakelag-validation:local`, sin red ni gameservers:
  `make build-exts-linux test-exts-linux test-ci`. Dieciocho pruebas Python,
  servicio/codec x86 y cadena SourceHook con objeto sintético correctos.
- `python3 scripts/run-native-tests.py --platform linux --sanitize`: ASan/UBSan
  del servicio/codec en host x64, correcto. No prueba la VM ni el ABI del juego.
- `make package-smx package-exts-linux release-linux validate-artifact`: correcto
  en el contenedor; ZIP combinado local en `dist/release/l4d2-speedwatch-local-linux.zip`.
- `actionlint .github/workflows/sourcemod-build.yml` y `git diff --check`: correctos.
- Sin compilación Windows, publicación, despliegue ni aceptación SRCDS de 0.10.0.

### Mejoras de debug del mismo candidato

Se amplía la validación aislada a veinte pruebas Python. Las de ventanas comprueban
los motivos simultáneos y que la admisión conserva sus reglas. Las de logging
ejercitan funciones de producción con dobles C++: contexto con máscara samples-only,
mapa todavía ausente, mapas largos, debug/máscara desactivados, correlación high:low,
alertas independientes de debug y rechazo de contexto de otra conexión. La adaptación
de varargs no ejecuta VFormat de SourcePawn; sus índices se comprueban por separado
y la compilación real de producción/consumidores sigue siendo obligatoria.

La comprobación efectiva del archivo y los cambios de debug en SourceMod siguen
pendientes de una prueba runtime autorizada. No se cambian rotación ni reapertura.

### Regresión del descarte por dropped_packets

Se elimina el veto automático por drops. La prueba adicional ejecuta las funciones
SourcePawn de producción adaptadas a C++ y comprueba:

- Cadencia normal con drops: ventanas admitidas, sin nueva gracia ni sospecha.
- Cinco ventanas inactivas y una ráfaga de 444 intentos: no abre episodio.
- Dos ráfagas consecutivas de 444 intentos, luego cadencia normal: no abre episodio.
- Ráfagas aisladas repetidas: cortan la racha aunque quede deuda acotada.
- Secuencia observada de 337, 133, 227, 444, 416, 267 y 335 intentos en ventanas
  de aproximadamente un segundo, con sus drops: abre un único episodio Active
  en la tercera muestra con los defaults, sin reiniciar gracia por drops.

Veintiuna pruebas Python correctas; producción y tres consumidores de API compilan
con SourcePawn 1.12.0.7255 y warnings tratados como errores. Es regresión aislada,
no replay de tráfico dentro del motor: quedan pendientes el retest de este fix en
comp-dev y la calibración con tráfico legítimo. No se despliega desde esta tarea.
