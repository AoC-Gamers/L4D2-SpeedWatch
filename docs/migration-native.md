# Migración nativa 0.12.0 y rollback

[Índice](index.md) · [Contrato nativo](native-core/index.md) · [Validación](testing.md)

## Decisiones y alcance

Se conserva la API pública de SpeedWatch para BanSystem, sin shim ni collector
heredado. `SpeedWatch_OnDetectionPersistence` sigue emitiendo cada 30 segundos
consecutivos de exceso confirmado después de Active; la ventana que lo inicia
no se cuenta. Normalidad, cero actividad o pérdida de confirmación cortan el
intervalo parcial. Demo conserva el incidente y obtiene el tick SourceTV real.

El core es obligatorio al cargar; API incompatible falla explícitamente. Sin
capacidades suficientes se suspende la regla con diagnóstico normal. No se
sustituyen intentos por bloques ni se exige contexto físico no implementado.
Ventanas 0.5–2 s, retención 2 s, lease 2.5 s; el servicio tiene la autoridad.
No se modifican umbrales de cadencia ni la opción de avisos públicos; siguen
pendientes calibración, CPU, memoria, I/O y aceptación SRCDS bajo carga comparable.

## Orden de migración

1. Inventariar consumidores: plugin y diagnóstico nativo consumen API v2;
   BanSystem Demo consume el include público, sin cambios. Recompilar estos
   consumidores y verificar las firmas de estados/persistencia.
2. Compilar SMX y extensión de la misma versión/plataforma. La API nativa v1
   se rechaza; no reutilizar su buffer con otra versión implícita.
3. Preparar el ZIP validado, configuración y respaldo privado de los binarios
   vigentes. Para una instalación futura autorizada, sustituir el conjunto y
   reiniciar/verificar las versiones, capacidades y ausencia de errores.
4. Retirar `sm_speedwatch_core_compare`; mantener rate/burst/samples,
   grace/cooldown/recovery y flags documentados. No distribuir pruebas.
5. Acreditar por separado detección real, callbacks de Demo, incidente compartido,
   ticks, cierre y entrega central. La compilación no acredita estas etapas.

## Rollback sin collector paralelo

El rollback consiste en reinstalar un conjunto anterior verificado, incluyendo
SMX, extensión y configuración correspondiente. No hay código legacy ejecutable
ni ConVar de comparación dentro de la distribución actual.

El inventario local solo contiene `channel/develop` y `channel/latest`: son tags
de canal mutables, **no puntos de rollback inmutables**. Antes de publicar esta
migración se debe seleccionar y preservar un tag de versión inmutable con su
commit y checksums; esta tarea no crea tags ni publica. Hasta entonces, los
respaldos privados con hashes permiten recuperación operativa del conjunto
instalado, pero no se presentan como una release/tag de rollback existente.

La investigación previa permanece identificada como histórica en evidencia y
validación del core. Los módulos retirados quedan en Git, no en `legacy/`.

## Aceptación pendiente

Sin desplegar en este encargo: carga temprana/tardía, pérdida/recuperación del
controlador/core, readyup/pausa, mapas/modos, huecos y cambios de identidad en
SRCDS. Probar un episodio >60 s con dos marcadores del mismo incidente y ticks
propios distintos. Comparar CPU/memoria/I/O y falsas sospechas con un corte
anterior identificado mediante herramientas separadas de laboratorio. No se
promete mejor precisión ni menor coste sin esas mediciones.
