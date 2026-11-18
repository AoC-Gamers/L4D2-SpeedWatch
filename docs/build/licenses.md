# Licencias y procedencia

El código y los recursos propios de SpeedWatch se distribuyen bajo
GPL-3.0-or-later según la declaración del proyecto. El inventario agrupa
rutas que comparten procedencia. Las cabeceras existentes identifican las
excepciones y los titulares donde constan.

| Rutas | Licencia y procedencia |
| --- | --- |
| `addons/sourcemod/scripting/l4d2_speedwatch*.sp`, módulos bajo `addons/sourcemod/scripting/l4d2_speedwatch/`, includes `l4d2_speedwatch*.inc`, traducciones y `extension/` | Código y recursos propios de SpeedWatch, GPL-3.0-or-later. La autoría del plugin consta en su entrypoint y el historial del repositorio. |
| `addons/sourcemod/scripting/include/left4dhooks*.inc` | Copias de Left4DHooks. Se conservan la licencia, titulares y excepciones de cada cabecera. |
| `addons/sourcemod/scripting/include/pause.inc` y `readyup.inc` | Includes externos bajo GPL-3.0-or-later según sus cabeceras. Se conservan las atribuciones originales. |
| `AMBuildScript`, `configure.py` | Adaptados de Custom-Fakelag en la revisión indicada en sus cabeceras, que identifican GPL-3.0. |
| `scripts/tools/make_sonar.py`, `tests/helpers/native_coverage.py`, `tests/tooling/sonar_tooling_test.py` | Adaptaciones de SteamWorks bajo GPL-3.0-or-later según sus cabeceras. |
| `Makefile`, `PackageScript`, reglas de Git y CI, plantillas `.env*.example`, demás `scripts/` y `tests/`, README, changelog y `docs/` | Archivos propios bajo la licencia del proyecto, incluidas las entradas JSON de selección y dependencias. |
| `LICENSE` | Textos legales y atribuciones. SourceMod, GPLv2 y SourceHook provienen de los SDK fijados. Los textos de GCC y glibc se tomaron de las licencias de la toolchain Linux. AMTL conserva los avisos de los headers identificados por las órdenes de compilación Linux. |

El archivo `LICENSE` del instalador reúne la licencia de SpeedWatch, los avisos
de SourceMod, SourceHook y AMTL, y la atribución al SDK L4D2. El enlazado Linux incluye código auxiliar de
`libgcc` y glibc, con sus textos legales seleccionados en el instalador. El mapa de enlace del build Linux x86 comprobado
no muestra objetos extraídos de los archivos estáticos `tier1_i486.a` y
`mathlib_i486.a`. Queda pendiente revisar la procedencia y condiciones del código
procedente de headers de Valve y la composición del enlace real de Windows. Las revisiones de SDK necesarias para reconstruir el binario
quedan fijadas en el lock. Los enlaces del paquete apuntan al repositorio en el
SHA de la compilación para consultar las fuentes de esa revisión.
