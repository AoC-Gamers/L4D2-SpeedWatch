# Documentación de L4D2 SpeedWatch

[README del proyecto](../README.md)

Documentación del plugin L4D2 SpeedWatch 0.8.0. Elegir la guía según el trabajo que se vaya a realizar.

| Guía | Contenido |
| --- | --- |
| [Instalación y configuración](installation.md) | Requisitos, compilación Linux, archivos de instalación, ConVars, permisos y status |
| [Build y CI/CD](build-system.md) | Manifiesto, targets, workflow, validación del paquete y canales de releases |
| [Arquitectura](architecture.md) | Alcance de la señal, runtime, mapa y observación, regla de sospecha y coste esperado |
| [Integraciones opcionales](integrations.md) | Contratos y comportamiento de Left4DHooks, pause y readyup; carga tardía y sincronización |
| [Logs y debug](logging.md) | Ruta, ConVars, máscara de flags, registros obligatorios, append, fallos y migración de cfg |
| [API pública](api.md) | Include, biblioteca, identidad, alertas, consulta de muestras y consumidor de diagnóstico |
| [Episodios y grabación](recording.md) | Active, Recovered, Interrupted, recuperación, motivos, callbacks y política del grabador |
| [Validación](testing.md) | Evidencia local y matriz pendiente de SRCDS, API, proveedores, logger y coste de CPU |

## Rutas de lectura

- Para instalar y ajustar el detector: instalación → integraciones → logs → validación.
- Para integrar otro plugin: API → episodios y grabación → validación.
- Para modificar el detector: arquitectura → integraciones → API → validación.

Los contratos públicos se declaran en
`addons/sourcemod/scripting/include/l4d2_speedwatch.inc`. La documentación explica
su uso; los cambios de firma o estructura requieren revisar y recompilar a sus
consumidores.

La evidencia de compilación y revisión estática se mantiene separada de las
pruebas de comportamiento pendientes en SRCDS, centralizadas en la guía de validación.
