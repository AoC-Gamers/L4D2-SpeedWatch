# Validación del núcleo nativo

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
- Sin extensión: conectar humanos, consultar API antigua y generar evidencia
  controlada legítima; confirmar mismos umbrales/cooldowns/episodios y sin errores.
- Con extensión: comparar muestras identificadas con el callback heredado. Repetir
  1v1/2v2/3v3/4v4, equipos desiguales, práctica con uno, cero, >8 y slots altos.
- Bots, espectadores y admins espectadores: sin registros analíticos para los dos
  primeros; conservar recepción de avisos y permisos del administrador.
- Conectar/desconectar, autorizar tarde, reutilizar slots, morir/respawnear,
  cambiar equipo/control/personaje, takeover de bot, clase, fantasma/materialización.
  Las muestras deben pertenecer al userid/serial correcto y el grupo físico ausente.
- Pausa/readyup/countdown/live, cambio de mapa, reinicio y ambas mitades Versus.
  Preservar `versusEndForwardObserved`, su respaldo y las interrupciones únicas.
- Descargar/recargar core, cambiar compare, quitar offset RunCommand en instalación
  aislada y probar carga parcial fallida. API incompatible y natives no presentes:
  detector heredado utilizable, sin recuperación ficticia ni muestras mezcladas.
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
nuevos y gracia. Las muestras nativas son diagnóstico experimental; ningún ensayo
requiere un cheat, inyector o alterar el tráfico del juego desde el core.

## Evidencia local de esta implementación

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
