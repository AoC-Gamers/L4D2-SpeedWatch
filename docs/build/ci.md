# CI, canales y publicación

[Build](README.md) · [Índice](../README.md)

`.github/workflows/sourcemod-build.yml` prepara hosts, cachés y transporte de
artefactos. Las operaciones de producto usan Make. Se conservan jobs separados
para dependencias, SMX, nativo Linux/Windows, paquetes y publicación; no se publica
hasta validar ambos sistemas. No se ejecutan Sonar ni cobertura en Actions.

`make release-identity` resuelve una identidad compartida para el flujo completo:

| Ref | Tag | Assets |
| --- | --- | --- |
| main | channel/latest | l4d2-speedwatch-latest-linux.zip / l4d2-speedwatch-latest-windows.zip |
| develop | channel/develop | l4d2-speedwatch-develop-linux.zip / l4d2-speedwatch-develop-windows.zip |
| v1.2.3 | v1.2.3 | l4d2-speedwatch-1.2.3-linux.zip / l4d2-speedwatch-1.2.3-windows.zip |
| PR/otro ref | Ninguno | Diagnóstico con SHA; nunca se promueve a un canal |

Latest es normal/Latest; Develop es prerelease/no Latest. Las versiones usan
su tag sin renombrarlo. El helper distingue el indicador GitHub Latest del tag
`channel/latest`. Para descargas estables, usar tag y nombre exactos del asset.

El job explícito de publicación verifica el par, SHA, plataforma y hashes, y
acceso al listado antes de mutar. En canales mueve el tag, retira la release
anterior sin borrar el tag, crea borrador, sube ambos ZIP y solo entonces publica.
No es atómico: puede haber una ventana sin descarga; un upload fallido deja un
borrador, sin rollback automático. Los reintentos deben ser explícitos. La
concurrencia por ref no cancela otra ejecución de ese ref.

Las notas de canal son mínimas: canal, UTC, commit/enlace y URL/intento de CI.
Cada job de release transporta su recibo en un artefacto de CI separado del ZIP.
El publicador exige ambos recibos, valida SHA, plataforma e integridad del par y
sube únicamente los dos ZIP a GitHub Releases. Los recibos y `build-info` no se
incluyen en los paquetes ni se agregan como assets de la release.
Los permisos de escritura están limitados al job de publicación. Una ejecución
local de `release-*` no usa credenciales, gh ni Git y nunca publica. El target
`publish-channel` exige `PUBLISH=1` y datos de CI; no forma parte de builds/tests.
Sus pruebas utilizan dobles de Git/gh sin contactar servicios.

## Runners del build nativo

GitHub Actions requiere acceso a las variables de organización
`L4D2_EXT_LINUX_RUNNER` y `L4D2_EXT_WINDOWS_RUNNER`. Un job por plataforma
valida su variable y detiene esa ruta si está ausente, vacía o contiene solo
espacios. La etiqueta validada se usa para resolver dependencias, compilar,
empaquetar y separar las cachés nativas por imagen del runner.

## Migración de nombres

Los assets anteriores `l4d2-speedwatch-linux-develop.zip` y equivalentes cambian
al orden canónico canal/plataforma de la tabla. Los consumidores que construyen
URLs deben actualizarse antes de adoptar una publicación con estos nombres.
Este cambio del repositorio no modifica hooks ni instalaciones externas.
