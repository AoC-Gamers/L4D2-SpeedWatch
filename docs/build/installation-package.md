# Instalación de L4D2 SpeedWatch

Revisión @REVISION@. Paquete para @PLATFORM@.

1. Usa Left 4 Dead 2 x86, SourceMod y Metamod compatibles y la gamedata
   `sdktools.games` de SDKTools.
2. Descomprime en el directorio del juego que contiene `addons/`. Conserva una
   copia del plugin y la extensión anteriores antes de actualizar. Retira las
   copias con el nombre antiguo `l4d2_speedwatch_core.ext.so` o `.ext.dll` para
   que solo quede la extensión del paquete.
3. Comprueba la carga con `sm exts list` y `sm plugins list`. Consulta
   `sm_speedwatch_status` para comprobar que el core está disponible.
4. Para revertir, restaura juntos el SMX y la extensión de la versión anterior.

SpeedWatch observa y comunica exceso sostenido de comandos. No aplica sanciones
automáticas. Consulta la [guía de instalación](@DOCS@/docs/installation/README.md)
y la [documentación del proyecto](@DOCS@/docs/README.md).
Consulta el [historial de cambios](CHANGELOG.md) incluido en el paquete.
La licencia del proyecto y los avisos de terceros están en `LICENSE`.
