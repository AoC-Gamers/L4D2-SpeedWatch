# Changelog

## [Unreleased]

**Antes de actualizar:** instala el plugin y el core nativo del mismo paquete.
Retira las copias de la extensión con el nombre anterior. Consulta la
[guía de instalación](README.md).

### Añadido

- **Diagnóstico:** las alertas y las muestras de depuración registran el estado
  de movimiento del jugador, correlacionado con la ventana del detector nativo.

### Cambiado

- **Distribución:** los ZIP de Linux y Windows incluyen las fuentes SourcePawn
  de producción, la API pública, las traducciones, la guía de instalación,
  la licencia y este changelog.
- **Distribución:** **INCOMPATIBLE** para instaladores que construyen las URL
  de descarga. Usa `l4d2-speedwatch-<canal>-<plataforma>.zip`, por ejemplo
  `l4d2-speedwatch-develop-linux.zip`. La extensión se instala con el sufijo
  `.ext.2.l4d2.so` en Linux o `.ext.2.l4d2.dll` en Windows.

### Corregido

- **Empaquetado:** la validación de rutas relativas funciona en Windows y
  permite generar el ZIP nativo con el mismo contrato de contenido que en Linux.

### Desarrollo

- **Compilación:** el Makefile raíz concentra la compilación, las pruebas,
  el empaquetado y la validación para uso local y CI.
- **Análisis estático:** configura Sonar en `.env` y guarda el token en
  `.env.secret` o en la variable `SONAR_TOKEN`. Usa `make sonar` para
  ejecutar el análisis de forma explícita.
