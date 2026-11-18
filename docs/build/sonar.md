# Análisis y cobertura locales

[Build](README.md) · [Índice](../README.md)

El producto integra SonarQube Community mediante Cppcheck y el plugin sonar-cxx.
Es distinto de SonarCFamily/Build Wrapper. No se instala ni configura un servidor,
no se crean proyectos/tokens y no se envía código durante build, tests o CI.
El tooling se adapta de SteamWorks (GPL-3.0-or-later); conserva contexto real,
fallos del parser, privacidad de credenciales y validación de cobertura.

## Configuración y ejecución explícita

Instalar explícitamente herramientas compatibles (Cppcheck, SonarScanner y plugin
sonar-cxx en el servidor). Copiar `.env.example` a `.env` y configurar URL HTTPS,
clave/nombre del proyecto y espera del gate. La codificación, fuentes, exclusiones,
sufijos C++ y recuperación del parser también se definen allí mediante
`SONAR_SOURCE_ENCODING`, `SONAR_SOURCES`, `SONAR_EXCLUSIONS`,
`SONAR_CXX_FILE_SUFFIXES` y `SONAR_CXX_ERROR_RECOVERY_ENABLED`.
`SONAR_PYTHON_VERSION=3.12` mantiene el análisis alineado con el entorno de build.
No hay `sonar-project.properties`: el wrapper lee `.env` como datos y transmite
las opciones al scanner, con precedencia del entorno explícito. La recuperación
CXX debe conservar el valor `false`; no se relaja el parser. Token por entorno `SONAR_TOKEN` o
`.env.secret` ignorado con permisos 600 (plantilla `.env.secret.example`); no ponerlo en `.env`, argumentos o commits.
Solo HTTP de loopback es admisible. La configuración se lee como datos, no shell.

```sh
make build-exts-linux
make sonar-cppcheck
# Solo cuando se quiera enviar el análisis al servidor configurado:
make sonar
```

El build exporta las tareas reales de AMBuild en `compile_commands.json`, con
arquitectura x86, directorio, SDK y flags. El analizador consulta macros/includes
con esos mismos flags sin producir objetos. No se inventan macros ni se silencian
atributos para el parser. Se rechazan bases incompletas e informes Cppcheck
inválidos; `sonar.cxx.errorRecoveryEnabled=false` impide métricas parciales.
Sonar espera la tarea y el quality gate, sin rebajar umbrales ni ampliar exclusiones.
El comando también rechaza errores registrados por el scanner aunque este devuelva
éxito y el servidor apruebe el gate; el resultado parcial no valida el producto.

## Cobertura medida

```sh
make deps-test-coverage
make test-coverage TEST_OUTPUT=.build/coverage/native
make test-python-coverage TEST_OUTPUT=.build/coverage/python
make sonar-tooling-test coverage-tooling-test
```

`TEST_OUTPUT` debe ser nuevo y se interpreta desde el directorio del llamador.
GCC/gcov mide pruebas x86 sobre servicio/codec y SourceHook; unidades productivas
no ejecutadas conservan líneas sin hits desde sus órdenes reales de compilación.
No se atribuyen hits de dobles, SDK, fixtures o binarios modificados a producto.
Python usa coverage.py 7.13.5, incluidos subprocesos. No hay cobertura SourcePawn
estimada a partir de assertions ni una afirmación de cobertura de ramas.
La medición Python ejecuta las regresiones del producto y las suites locales de
tooling; estas últimas permanecen fuera de CI. Solo se atribuyen hits sobre los
scripts canónicos, conservando como no cubiertos los scripts no ejecutados.
Las regresiones de comandos usan directorios temporales y proveedores externos
controlados para verificar hashes, revisiones, propagación de fallos y límites de
limpieza sin descargar SDK ni publicar. Las pruebas de entorno MSVC modelan su
salida; no equivalen a una compilación Windows. Los contadores nativos siguen
siendo independientes de estas pruebas Python.

Cada informe genérico incluye un receipt con huellas de fuentes y del XML.
Tras cambiar fuentes o tooling, regenerarlo. Configurar opcionalmente
`SONAR_COVERAGE_RECEIPT` y `SONAR_PYTHON_COVERAGE_RECEIPT`; informes alterados,
obsoletos o de otro tipo bloquean el scanner. Un informe de líneas no acredita ABI,
VM ni SRCDS. Los artefactos de análisis no forman parte del instalador.

Sonar, sus pruebas de tooling y los ejecutores de cobertura quedan fuera de
`test-ci` y GitHub Actions. Las regresiones del producto permanecen en CI.

## Validación local de cobertura

Se realizaron pruebas locales con 59 regresiones de producto/pipeline y 31 de
tooling. Sonar midió 85,0 % global sobre 1.287 líneas ejecutables, con cero
hallazgos abiertos y quality gate aprobado. Python registró 981/1.042 líneas;
el informe nativo x86, 113/245. Se conservaron umbrales, exclusiones y líneas
no ejecutadas. La mejora global no implica un 80 % de cobertura nativa ni
acredita comportamiento en SRCDS o una compilación Windows.
