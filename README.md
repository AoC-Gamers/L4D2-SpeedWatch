# L4D2 SpeedWatch 0.8.0

[![SourceMod Build](https://github.com/AoC-Gamers/L4D2-SpeedWatch/actions/workflows/sourcemod-build.yml/badge.svg)](https://github.com/AoC-Gamers/L4D2-SpeedWatch/actions/workflows/sourcemod-build.yml)

Prototipo independiente de SourceMod para observar exceso sostenido de comandos
de movimiento y enviar sospechas al chat. No bloquea comandos, no altera el
movimiento y no ejecuta kick ni ban. Funciona sin SMAC, Left4DHooks ni colors.inc.

La detección observa exceso sostenido de comandos. La recuperación informa de
cadencia normal observada; no acredita que un cheat se haya desactivado.

Repositorio: [AoC-Gamers/L4D2-SpeedWatch](https://github.com/AoC-Gamers/L4D2-SpeedWatch).
Los paquetes compilados se publican en [Releases](https://github.com/AoC-Gamers/L4D2-SpeedWatch/releases).

## Documentación

El punto de entrada es [docs/index.md](docs/index.md).

| Tema | Guía |
| --- | --- |
| Compilar, instalar, configurar ConVars y consultar estado | [Instalación y configuración](docs/installation.md) |
| Compilación, artefactos, canales y exclusión del test en CI | [Build y CI/CD](docs/build-system.md) |
| Señal, umbrales, ciclo de observación y coste esperado | [Arquitectura](docs/architecture.md) |
| Left4DHooks, pause y readyup opcionales | [Integraciones](docs/integrations.md) |
| Archivo de log, debug y flags | [Logs y debug](docs/logging.md) |
| Include, biblioteca, native y forward de alertas | [API pública](docs/api.md) |
| Estados Active, Recovered e Interrupted para un grabador | [Episodios y grabación](docs/recording.md) |
| Evidencia local y pruebas pendientes en SRCDS | [Validación](docs/testing.md) |

## Estado del prototipo

La versión 0.8.0 y los consumidores de API opcional y obligatorio compilan con
SourcePawn 1.12.0.7255 y `-E`, sin warnings. Las pruebas en SRCDS, la integración
real con un grabador y la medición de CPU siguen pendientes. No se ha desplegado
en un servidor.

Licencia: GPL-3.0-or-later; consultar `LICENSE`.
