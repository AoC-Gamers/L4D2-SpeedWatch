# Pruebas

[Build y dependencias](../docs/build/README.md) · [Contrato del detector](../docs/testing/README.md)

```sh
make build-smx build-api-test
make test-ci
make test-exts-linux test-native-sanitized
make test TEST_OUTPUT=.build/tests/local-run
make sonar-tooling-test coverage-tooling-test
```

`test-ci` descubre regresiones de producto y pipeline en `tests/python`.
`tests/native` ejecuta servicio/codec y SourceHook real sobre objetos sintéticos;
no carga SDK en un juego. Los arneses SourcePawn de `tests/diagnostics` se compilan
como consumidores y se excluyen del instalador. `tests/tooling` valida Sonar y
cobertura solo localmente. `tests/helpers` contiene adaptadores, no producto.

Los contratos de comandos ejecutan los scripts canónicos contra archivos
temporales y proveedores externos controlados. Cubren hashes y revisiones del
SDK, fallos de compilación, exportación de órdenes reales, límites de limpieza,
metadatos y filtrado del entorno MSVC, sin descargar ni publicar durante las pruebas.

`test` exige una salida nueva, relativa al cwd del llamador, y propaga el primer
fallo; no descarga dependencias. Compilación y dobles no acreditan VM, gameplay,
ABI runtime ni precisión del detector. Windows necesita su toolchain real.
