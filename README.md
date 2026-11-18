# L4D2 SpeedWatch 0.12.0

[![SourceMod Build](https://github.com/AoC-Gamers/L4D2-SpeedWatch/actions/workflows/sourcemod-build.yml/badge.svg)](https://github.com/AoC-Gamers/L4D2-SpeedWatch/actions/workflows/sourcemod-build.yml)

Plugin de SourceMod para Left 4 Dead 2 que detecta exceso sostenido de comandos
de movimiento y comunica posibles casos de speedhack mediante alertas de chat,
logs y una API para otros plugins. No bloquea comandos, no altera el movimiento
y no ejecuta kick ni ban. Funciona sin SMAC, Left4DHooks ni colors.inc.

La detección observa exceso sostenido de comandos. La recuperación informa de
cadencia normal observada; no acredita que un cheat se haya desactivado.

Repositorio: [AoC-Gamers/L4D2-SpeedWatch](https://github.com/AoC-Gamers/L4D2-SpeedWatch).
Los paquetes compilados se publican en [Releases](https://github.com/AoC-Gamers/L4D2-SpeedWatch/releases).

La versión 0.10.0 utiliza exclusivamente las ventanas del
[núcleo nativo](docs/native-core/README.md) para detectar cadencia excesiva de
intentos de `PlayerRunCommand`. No cuenta callbacks SourcePawn ni ofrece fallback
al detector anterior. Sin core compatible o sin muestras válidas, interrumpe la
observación. Estos intentos no acreditan ejecución original ni velocidad física.

La API 0.11.0 añade [marcadores de persistencia](docs/integrations/speedwatch-persistence.md)
cada 30 segundos consecutivos de exceso confirmado, dentro del mismo episodio.

## Funcionalidades

- Evaluación compartida cada segundo, con margen, buffer, gracia y umbral configurables.
- Alertas para administradores o chat público, con cooldown por jugador.
- [Contexto diagnóstico L4D2](docs/context/README.md) en muestras debug y alertas, sin modificar la regla de detección.
- Registro obligatorio de detecciones y transiciones; debug mediante ConVars y flags.
- API con client, AccountID, userid y consulta de la última muestra válida.
- Episodios Active, Recovered e Interrupted para coordinar grabaciones externas.
- Integraciones opcionales con pause, readyup y Left4DHooks.
- Código SourcePawn modular compilado en un único SMX y extensión C++ por plataforma, obligatoria al cargar.

## Documentación

El punto de entrada es [docs/README.md](docs/README.md).

| Tema | Guía |
| --- | --- |
| Compilar, instalar, configurar ConVars y consultar estado | [Instalación y configuración](docs/installation/README.md) |
| Compilación, artefactos, canales y exclusión del test en CI | [Build y CI/CD](docs/build/README.md) |
| Señal, umbrales, ciclo de observación y coste esperado | [Arquitectura](docs/architecture/README.md) |
| Left4DHooks, pause y readyup opcionales | [Integraciones](docs/integrations/README.md) |
| Archivo de log, debug y flags | [Logs y debug](docs/logging/README.md) |
| Include, biblioteca, native y forward de alertas | [API pública](docs/api/README.md) |
| Estados Active, Recovered e Interrupted para un grabador | [Episodios y grabación](docs/recording/README.md) |
| Evidencia local y pruebas pendientes en SRCDS | [Validación](docs/testing/README.md) |

## Validación

Producción y consumidores de API compilan con SourcePawn 1.12.0.7255 y `-E`.
El core compila en Linux x86 y Windows x86 con sus toolchains nativos. CI valida
ELF/PE, exports y paquetes de ambos sistemas, con pruebas del servicio/codec
y SourceHook sobre objetos sintéticos. SRCDS y rendimiento siguen pendientes;
consultar [validación nativa](docs/native-core/validation.md).

Licencia: GPL-3.0-or-later; consultar `LICENSE`.

- [Migración nativa y rollback](docs/migration-native/README.md).
