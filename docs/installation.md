# Compilación, instalación y configuración

[Índice de documentación](index.md) · [README](../README.md)

Ejecutar los comandos de compilación desde la raíz del proyecto.
Las rutas del código y del build se expresan respecto a esa raíz.

## Compilación Linux

Se requiere Python con soporte `tarfile` para `filter="data"`, `make`, y un
compilador SourcePawn de SourceMod 1.12. El helper descarga la rama oficial 1.12
y reutiliza un SDK existente; el número de build no está fijado.
El build añade `addons/sourcemod/scripting/include` para usar la copia de
`pause.inc` y `readyup.inc`; ambas dependencias de runtime son opcionales.

```bash
make deps-smx
make build-smx
```

Salida: `.build/smx/addons/sourcemod/plugins/l4d2_speedwatch.smx`. `-E` trata warnings como errores.
También puede usarse un SDK existente:

```bash
make build-smx SM_SCRIPTING=/ruta/al/sdk/addons/sourcemod/scripting
```

El manifiesto `plugin-package-map.json` limita el build a `l4d2_speedwatch`;
el test no se compila en este target. Para empaquetado y automatización, consultar
[build y CI/CD](build-system.md).

## Instalación

Copiar únicamente:

```text
.build/smx/addons/sourcemod/plugins/l4d2_speedwatch.smx
  → addons/sourcemod/plugins/l4d2_speedwatch.smx
addons/sourcemod/translations/l4d2_speedwatch.phrases.txt
  → addons/sourcemod/translations/l4d2_speedwatch.phrases.txt
```

SDKTools y SDKHooks deben estar disponibles en SourceMod; sus includes conservan
la carga automática y el requisito estándar. Pause, readyup y Left4DHooks siguen
siendo plugins opcionales.

Cargar desde consola con `sm plugins load l4d2_speedwatch`. SourceMod genera
`cfg/sourcemod/l4d2_speedwatch.cfg`. Configurar las ConVars según las necesidades
del servidor; los escenarios de validación en juego están en [validación](testing.md).

## Configuración

| ConVar | Default | Función |
| --- | --- | --- |
| `sm_speedwatch_enable` | `1` | Activa observación |
| `sm_speedwatch_rate` | `1.10` | Margen sobre tickrate |
| `sm_speedwatch_burst` | `2.0` | Buffer en segundos de ticks nominales |
| `sm_speedwatch_samples` | `3` | Muestras consecutivas requeridas |
| `sm_speedwatch_grace` | `5.0` | Gracia en segundos |
| `sm_speedwatch_cooldown` | `30.0` | Separación mínima entre alertas por cliente |
| `sm_speedwatch_recovery_time` | `5.0` | Segundos consecutivos de cadencia normal para recuperar un episodio (1–60) |
| `sm_speedwatch_public` | `0` | `0`: admins; `1`: todos |
| `sm_speedwatch_debug` | `0` | `0`: debug apagado; `1`: debug activo |
| `sm_speedwatch_debug_flags` | `15` | Máscara de categorías de debug (0–31) |

## Alertas y permisos

Admins con flag genérico (`b`) reciben alertas por defecto. El override
`sm_speedwatch_alerts` permite cambiar los receptores sin registrar un comando
con ese nombre. Para mostrar alertas públicas:

```text
sm_cvar sm_speedwatch_public 1
```

Ejemplo de chat en español, según idioma del receptor:

```text
[SpeedWatch] Posible speedhack: Jugador (#42), 45.0 cmds/s (1.50x tickrate).
```

## Consulta de estado

Comando `sm_speedwatch_status` (admin genérico o consola): muestra la última
muestra, tickrate, cadencia por humano, exceso, racha, gracia, episodio activo y
segundos acumulados de recuperación. Desde un cliente
conviene ejecutarlo en consola para leer todas las líneas. `ratio` es cadencia
de comandos / tickrate; no es un multiplicador medido de velocidad física.

Para configurar el archivo y sus flags, consultar [logs y debug](logging.md).
Antes de probar con proveedores, revisar [integraciones opcionales](integrations.md),
especialmente el escaneo de detours de Left4DHooks durante carga tardía.
