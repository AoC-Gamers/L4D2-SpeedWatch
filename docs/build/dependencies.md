# Dependencias y revisiones

[Build](README.md)

| Entrada | Fuente de verdad | Rol | Distribución |
| --- | --- | --- | --- |
| SourceMod Linux 1.12.0.7255 | `scripts/deps/sourcepawn-package.lock.json`: URL y SHA-256 | Compilador/headers de SourcePawn | Externa |
| HL2SDK L4D2, SourceMod, Metamod, AMBuild | `dependencies.lock.json`: commits completos | Build y pruebas nativas x86 | Externa |
| Includes Left4DHooks, pause y readyup | Fuentes vendorizadas, API/licencia de sus proveedores | Compilación; sus proveedores tienen contrato runtime propio | No se empaquetan |
| Include SpeedWatch y core | `addons/sourcemod/scripting/include/` | API propia pública y nativa v2 | Incluidos |
| Coverage.py 7.13.5 | `scripts/deps/fetch-test-coverage.py` | Cobertura local Python | Externa, `.deps/test-coverage` |
| Cppcheck, SonarScanner y sonar-cxx | Instalación explícita compatible con el servidor elegido | Análisis local explícito | Externos |

No se cambian revisiones por ordenar directorios. El build verifica commits del
lock y rechaza SDK con cambios versionados, archivos no versionados o entradas de
build adicionales ignoradas por Git. Solo permite los seis archivos de metadatos
`AMBuild.egg-info` generados por su instalación y copias bajo `build/lib/` cuyos
bytes coincidan con sus fuentes versionadas. No permite fuentes nuevas ni copias
modificadas en esos directorios. No descarga dependencias durante el build. Los fetches
ocurren solo mediante `deps-*`. Los submódulos se resuelven desde esos commits.
El build recorre los submódulos inicializados a cualquier profundidad, compara
su HEAD con el gitlink fijado por el padre y verifica sus archivos, incluidos los
ignorados por Git. Los opcionales no inicializados pueden estar ausentes o vacíos;
se rechazan si contienen archivos sin un checkout verificable. Esta comprobación
no inicializa submódulos ni amplía las dependencias descargadas.
El lock de fuentes/SDK no fija el compilador del host, paquetes del sistema o
versiones de análisis instaladas; no acredita reproducibilidad byte a byte.

El SDK SourcePawn gestionado requiere conservar el archivo descargado junto al
directorio extraído. Su hash, el marcador y los bytes del compilador/includes deben
coincidir con el paquete fijado; agregar o modificar un include invalida la
verificación. Un SDK externo se admite como `external`, con hashes reales y sin
atribuirle el lock. El build comprueba que sus entradas no cambien al compilar.

Al actualizar una dependencia: revisar consumidores/ABI, resolver revisión/hash,
actualizar la fuente canónica y cachés pertinentes, recompilar consumidores,
validar paquetes y documentar requisitos. La aceptación runtime es independiente.
