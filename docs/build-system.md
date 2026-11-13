# Build y CI/CD

[Índice](index.md) · [Núcleo nativo](native-core/index.md)

`make` es la entrada común. SourcePawn usa los scripts Python existentes y la
extensión usa AMBuild (`configure.py`, `AMBuildScript`, `extension/AMBuilder` y
`PackageScript`), adaptados de Custom-Fakelag `b871f52`. No hay CMake/Meson ni
compilación implícita al empaquetar.

## Linux x86

Requiere Python 3.12, git, make, g++ con multilib (`g++-multilib` en Ubuntu) y venv.
Los comandos de dependencias son los únicos que usan red:

```sh
make deps-smx deps-exts-linux
make build-smx build-api-test build-exts-linux
make test-exts-linux test-ci
python3 scripts/run-native-tests.py --platform linux --sanitize
make package-smx package-exts-linux
make release-linux validate-artifact
```

El build SourcePawn siempre usa `-E`. La extensión usa C++14, `-m32`, optimización,
visibilidad oculta y warnings fatales; el script registra la salida completa y
propaga cualquier error. Las pruebas unitarias ordinarias usan x86. Sanitizadores
sobre servicio aislado usan la arquitectura del host y no validan el ABI del juego.
`AbiChecks.cpp` forma parte de la extensión x86 y valida la firma SDK.

## Windows x86

Requiere Python 3.12, git, make y una terminal de MSVC inicializada para x86. CI usa
`ilammy/msvc-dev-cmd` con `arch: x86`. No se declara soporte de cross-build desde Linux.

```sh
make deps-exts-windows PYTHON=python
make build-exts-windows test-exts-windows PYTHON=python
make package-exts-windows PYTHON=python
make release-windows validate-artifact PLATFORM=windows PYTHON=python
```

El paquete SMX compartido se obtiene del job Linux o se copia como árbol existente
a `.build/package-smx`; no hace falta recompilarlo en Windows. `subprocess` con
`check=True` propaga fallos del compilador, configure, AMBuild, tests y git. No hay
un wrapper PowerShell que pueda ocultar errores de procesos externos.

## Dependencias y salidas

| Dominio | Dependencias | Build | Staging |
| --- | --- | --- | --- |
| SMX compartido | .deps/smx/sourcemod-linux | .build/smx | .build/package-smx |
| Extensión Linux x86 | .deps/exts-linux | .build/exts-linux | .build/package-exts-linux |
| Extensión Windows x86 | .deps/exts-windows | .build/exts-windows | .build/package-exts-windows |

Las dependencias nativas tienen commits fijados en `dependencies.lock.json`, con
submódulos fijados por esos repositorios. `resolved.json` registra la resolución.
No se actualiza una copia de dependencia sucia. SourcePawn usa el paquete
1.12.0.7255 fijado por URL/SHA256; la caché requiere su marcador de verificación.
Un destino antiguo no verificado exige elegir un destino limpio, no se reemplaza.

Se conservan `SPCOMP`, `SM_SCRIPTING`, `SMX_BUILD_DIR`, `SMX_PACKAGE_DIR`,
`SOURCEMOD_VERSION`/`SM_VERSION` (rama compatible 1.12) y `RELEASE_BASENAME`.
Los overrides nativos son `EXTS_LINUX_DEPS_DIR`, `EXTS_WINDOWS_DEPS_DIR`,
`LINUX_BUILD_DIR`, `WINDOWS_BUILD_DIR`, `EXTS_PACKAGE_LINUX_DIR`,
`EXTS_PACKAGE_WINDOWS_DIR`, `LINUX_RELEASE_BASENAME` y `WINDOWS_RELEASE_BASENAME`.
Los outputs deben estar dentro de `.build`/`dist`; no se limpia el checkout.
El build SourcePawn antiguo continúa disponible con `SPCOMP=deps/sourcemod-linux/
addons/sourcemod/scripting/spcomp64`; el directorio antiguo no es el default.

`make release` conserva un alias local: empaqueta las salidas existentes de SMX y
Linux y ejecuta `release-linux`. Ya no genera un ZIP ambiguo sin plataforma.
`make clean` llama a ambas limpiezas de plataforma; estas conservan los outputs
SMX compartidos y los ZIP existentes, evitando borrar el trabajo concurrente de
la otra plataforma. Se pueden retirar manualmente esos compartidos cuando no haya
builds en curso. Ningún target de package/release descarga un SDK ni recompila.

## Manifiesto y contenido de paquetes

`build.plugins` selecciona únicamente `l4d2_speedwatch.sp` como entrypoint.
`build.extensions` declara únicamente `l4d2_speedwatch_core`. Los módulos privados
se incluyen dentro del SMX y no se compilan como plugins independientes. Los tests
antiguos y nativo se compilan mediante `build-api-test` y nunca se distribuyen.

Cada ZIP contiene un SMX, una extensión de su plataforma, fuentes SourcePawn
permitidas, ambos includes públicos, traducciones, LICENSE, `compile.log`,
`native-compile.log`, `sourcepawn-build-info.json` y `build-info.json`. Los metadatos
registran SHA, dependencias, compiladores, inputs y hashes de binarios/payload.
No se exige `.so` y `.dll` juntos. Gamedata propia no se añade: se necesita la
`PlayerRunCmd` de SDKTools instalada con SourceMod. Quedan excluidos docs, README,
SDKs, tests, harnesses, includes de terceros y binarios del juego.

El empaquetado valida ELF32/PE32 x86, exports `GetSMExtAPI` y `CreateInterface_MMS`,
archivos faltantes/vacíos/no permitidos, duplicados de plataforma y hashes. Un
cambio de inputs impide presentar un binario antiguo como build de las fuentes
actuales. Las pruebas de empaquetado usan fixtures explícitos, no binarios reales
del juego. El archivo de metadata no es una firma criptográfica de autenticidad.

## Canales CI

El job `smx` compila el SMX compartido una vez, compila consumidores API, ejecuta
pruebas Python y prepara su staging. `native` compila/prueba cada plataforma y
prepara su staging. `release` combina únicamente salidas existentes, sin SDK, y
valida cada ZIP; falla si falta una etapa requerida. Las cachés son independientes
por plataforma x86 y lock de dependencias.

Solo `publish`, después de ambas releases, tiene permiso de escritura. Conserva
`channel/latest` para main y `channel/develop` como prerelease para develop.
Los PR producen artefactos sin tags/releases ni secretos para código de forks.
Los assets pasan a `l4d2-speedwatch-linux-latest.zip`,
`l4d2-speedwatch-windows-latest.zip` y sus equivalentes `-develop` o `-pr-<sha>`.
El antiguo asset sin plataforma se sustituye por esos dos nombres; los consumidores
deben seleccionar su plataforma. Preparar el workflow no implica haberlo ejecutado
ni autoriza publicación remota desde esta tarea.
