# Compilación y paquetes

[Índice](../README.md) · [Dependencias](dependencies.md) · [CI y canales](ci.md) · [Sonar local](sonar.md)

El Makefile raíz es la interfaz común local/CI. Los backends versionados viven en
`scripts/{deps,build,package,ci,tools}`; el build no depende de Obsidian ni de un
agente. AMBuild se conserva para C++; SourcePawn usa spcomp 1.12 y `-E`.
La fuente de versión sigue en el producto; no se crea otro archivo VERSION.

## Linux x86

Requisitos: GNU Make, Bash, Python 3.12, git, g++ con multilib y venv. Las descargas
solo ocurren con targets explícitos de dependencias:

```sh
make deps-smx deps-exts-linux
make build-smx build-api-test build-exts-linux
make test-ci test-exts-linux test-native-sanitized
make package-smx package-exts-linux
make release-linux validate-artifact-linux
make check-ci
```

`build-*` no descarga, `package-*` no compila y `release-*` no publica. El agregado
`make release` espera ambos stagings antes del ZIP, también con `-j`. Invocar
`make -j deps build package` sin dependencias de orden no crea un pipeline seguro.

## Windows x86

En un host Windows con GNU Make/Bash, Python y MSVC instalados:

```sh
make deps-smx deps-exts-windows PYTHON=python
make setup-msvc PYTHON=python
make test-exts-windows build-exts-windows PYTHON=python
make package-smx package-exts-windows PYTHON=python
make release-windows validate-artifact-windows PYTHON=python
```

`setup-msvc` exporta el entorno a GitHub Actions; localmente inicializar antes una
terminal MSVC x86. SourcePawn se compila una sola vez en Linux y se comparte el
árbol SMX/log validado entre ambas fases de paquetes. El SDK Linux de SourcePawn
no se ejecuta en Windows. Los tests PE con fixtures no sustituyen MSVC real.

## Rutas y ejecución desde otro directorio

Make ubica el repositorio desde su propio archivo, no desde el cwd ni `.git`:

```sh
make -f "/ruta con espacios/L4D2-SpeedWatch/Makefile" build-smx
make -f "/ruta con espacios/L4D2-SpeedWatch/Makefile" test TEST_OUTPUT=resultados-nuevos
```

Las variables de dependencias, compiladores, build y staging relativas se resuelven
desde el repositorio; admiten rutas absolutas. `TEST_OUTPUT` es la excepción
explícita: relativo al directorio del llamador y debe ser nuevo. `PYTHON` es
configurable. Un checkout de fuentes sin `.git` conserva los hashes; el campo de
commit nativo es null, nunca un SHA inventado o heredado de otro repositorio.

| Árbol | Contenido |
| --- | --- |
| `.deps/smx`, `.deps/exts-linux`, `.deps/exts-windows` | Dependencias externas |
| `.build/smx` | SMX, fuentes propias seleccionadas y procedencia |
| `.build/exts-<so>` | AMBuild, objetos, package, log y compile_commands.json |
| `.build/package-smx`, `.build/package-exts-<so>` | Stagings separados |
| `dist/linux/artifact`, `dist/windows/artifact` | Composición validada por SO |
| `dist/release` | ZIP local |
| `tests/diagnostics` | Consumidores de prueba SourcePawn, nunca instalables |

El paquete mixto usa una composición única por plataforma. No permitir copias
paralelas destructivas sobre la misma raíz. `clean-linux`/`clean-windows` eliminan
solo sus árboles nativos gestionados y preservan los resultados SMX compartidos.

## Contrato de producto

`scripts/package/package-map.json` es el único mapa, leído por el contrato común
`artifact_contract.py`, builders, staging y tests. No queda una copia en raíz.
Los diez módulos del plugin y la extensión propia se declaran explícitamente.
Se conserva la selección de fuentes propias y API del paquete de SpeedWatch;
SDK, includes externos, harnesses, informes, cachés y documentos se excluyen.
Los logs completos se conservan en los árboles de build/CI; no se copian al ZIP
instalable. Su metadata pública conserva versiones y hashes sin el entorno local.

Se rechazan faltantes, extras, symlinks, archivos especiales, traversal, colisiones
por mayúsculas, claves ignoradas y basenames inseguros. Se verifican arquitectura,
exports, hashes de binarios/fuentes y procedencia; no se rescata un binario viejo
tras un fallo. El ZIP final se vuelve a leer y comparar con el árbol validado.
Esto no acredita reproducibilidad byte a byte entre compiladores distintos.

La extensión canónica es `l4d2_speedwatch_core.ext.2.l4d2.so` en Linux y
`l4d2_speedwatch_core.ext.2.l4d2.dll` en Windows. Antes de instalar una publicación
nueva, descargar la extensión y retirar la copia antigua `.ext.so`/`.ext.dll`,
conservando un respaldo privado verificado. El loader resuelve el sufijo del
juego desde el include existente; no cambia la API nativa v2 ni el detector.
No se retiran archivos ni se instala nada por compilar este repositorio.

Los nombres de ZIP y la migración de sus consumidores están en [CI](ci.md).
La aceptación SRCDS, las mecánicas de juego y BanSystem son comprobaciones separadas.
