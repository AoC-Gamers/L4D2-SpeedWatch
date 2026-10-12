# Build y CI/CD

[Índice de documentación](index.md) · [README](../README.md)

El CI/CD separa dependencias, compilación y release en etapas, con scripts
compartidos entre `make` y GitHub Actions.
La plataforma del pipeline es Linux y usa SourceMod 1.12.

## Manifiesto de producción

`plugin-package-map.json` controla dos listas:

- `build.plugins`: entrypoints que se compilan. Solo declara `l4d2_speedwatch`.
- `artifact.addons.sourcemod`: fuentes, includes y traducciones publicados.

Los módulos privados `logging.sp`, `integrations.sp` y `detector.sp` se publican
en `addons/sourcemod/scripting/l4d2_speedwatch/`. Se incluyen desde el principal;
no se añaden a `build.plugins` ni generan SMX propios. El paquete conserva estos
archivos junto con el include público de la API. Los includes de terceros
(`pause`, `readyup` y `left4dhooks*`) permanecen en el checkout y se excluyen del
ZIP. Para recompilar con todas las dependencias, usar el checkout del repositorio.

`build-local.py` recorre exclusivamente los plugins declarados, sin compilar
por wildcard los `.sp` presentes en `scripting/`. La ausencia de una fuente
mapeada o cualquier warning/error de `spcomp` falla el build. Antes de compilar,
se recrea el directorio de salida para descartar SMX de ejecuciones anteriores.

`addons/sourcemod/scripting/l4d2_speedwatch_test.sp` se conserva en el checkout,
pero no está en el manifiesto de producción. El workflow no ejecuta
`make build-api-test`: no genera sus binarios opcional ni obligatorio. El test
tampoco se incluye como fuente en el ZIP de producción. Su compilación manual
sigue disponible según [API pública](api.md#consumidor-de-diagnóstico).

## Targets y salidas

Ejecutar desde la raíz del proyecto:

| Target | Función y salida |
| --- | --- |
| `make deps-smx` | Descarga o reutiliza el SDK en `deps/sourcemod-linux` |
| `make build-smx` | Compila producción y copia los archivos mapeados a `.build/smx/addons/sourcemod/`; registra `deps/build-smx-compile.log` |
| `make package-smx` | Crea `.build/package-smx` con addons, README, licencia, docs y compile.log |
| `make validate-artifact` | Valida `dist/sourcemod/artifact` contra el manifiesto y la documentación |
| `make release` | Prepara el paquete, lo lleva a `dist/sourcemod/artifact`, valida y genera `dist/release/l4d2-speedwatch-local.zip` |
| `make test-ci` | Ejecuta las pruebas de selección y empaquetado; no compila plugins de diagnóstico |
| `make build-api-test` | Compilación manual del test en `.build/tests/`, fuera de CI y del paquete |
| `make clean` | Elimina únicamente `.build/` y `dist/`; conserva el SDK |

Flujo local equivalente al build y release del workflow:

```bash
make test-ci
make deps-smx
make build-smx
make release RELEASE_BASENAME=l4d2-speedwatch-local
```

El binario de producción queda en
`.build/smx/addons/sourcemod/plugins/l4d2_speedwatch.smx`.
Los overrides `SM_SCRIPTING`, `SPCOMP` y `SM_VERSION` permiten seleccionar el SDK
y el compilador. `SOURCEMOD_VERSION` selecciona la rama del helper; actualmente admite
`1.12`. `PYTHON`, `SMX_BUILD_DIR`, `SMX_PACKAGE_DIR` y `RELEASE_BASENAME` ajustan
las herramientas y salidas. Los directorios generados deben quedar dentro de
`.build/` o `dist/`. El número de build del SDK no está fijado y la caché puede
conservar un SDK anterior de la misma rama.

## Workflow

Archivo: `.github/workflows/sourcemod-build.yml`.

Se ejecuta en pushes a `main` y `develop`, pull requests que afecten al código,
documentación o pipeline, y ejecución manual (`workflow_dispatch`).

1. `deps-smx`: restaura la caché del SDK; si falta, ejecuta `make deps-smx` y la guarda.
2. `build-smx`: restaura el SDK, ejecuta `make test-ci` y `make build-smx`.
   Sube por separado `.build/smx` y el log de compilación, retenidos un día.
3. `release`: descarga el build y el log, ejecuta `make release`, y sube el ZIP
   como artefacto de Actions retenido 14 días. En ramas de canal, publica también
   la release correspondiente.

Las etapas de dependencias y compilación tienen permiso `contents: read`.
Solo el job de release solicita `contents: write`. Las operaciones de tag y
publicación excluyen siempre los eventos `pull_request`.

## Canales de publicación

| Contexto | ZIP | Tag y release |
| --- | --- | --- |
| Push o ejecución manual en `main` | `l4d2-speedwatch-latest.zip` | `channel/latest`, Latest |
| Push o ejecución manual en `develop` | `l4d2-speedwatch-develop.zip` | `channel/develop`, Develop como prerelease |
| Pull request u otra rama manual | `l4d2-speedwatch-pr-<sha7>.zip` | Solo artefacto de Actions; no publica release |

Los tags de canal son móviles: el workflow los actualiza
al commit de la ejecución y reemplaza el asset del canal. No crea releases
versionadas por cada build ni despliega en un servidor de juego.

Repositorio público: [AoC-Gamers/L4D2-SpeedWatch](https://github.com/AoC-Gamers/L4D2-SpeedWatch).
La rama predeterminada es `main`; `develop` conserva el canal de desarrollo.
Consultar ejecuciones y artefactos en [GitHub Actions](https://github.com/AoC-Gamers/L4D2-SpeedWatch/actions/workflows/sourcemod-build.yml)
y paquetes publicados en [Releases](https://github.com/AoC-Gamers/L4D2-SpeedWatch/releases).
El resultado de cada ejecución corresponde al commit que muestra Actions; la
publicación de un paquete no acredita una prueba en SRCDS.

## Validación del paquete

`ci-validate-artifact.sh` y `validate-artifact.py` comprueban todos los archivos
esperados y rechazan archivos adicionales. Solo se admite el SMX declarado en
`build.plugins`; introducir un SMX de test o de otro plugin hace fallar el staging
y la creación del ZIP. También se exige un binario y un log no vacíos, README,
licencia, documentación, fuente principal, módulos privados, API y traducciones.

El ZIP es un paquete de instalación con las fuentes de producción y su
compilación registrada. Los scripts, workflow, manifiesto y test de diagnóstico
se mantienen en el checkout de desarrollo. Para modificar o recompilar el
proyecto completo, utilizar ese checkout.

Las pruebas locales de esta cadena y los escenarios pendientes de ejecución
remota y SRCDS están en [validación](testing.md#cadena-de-build-y-empaquetado).
