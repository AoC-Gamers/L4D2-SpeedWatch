# Changelog

## Sin publicar

### Cierre de revisión del build

- Rutas relativas del paquete compatibles con Windows, conservando el rechazo
  de raíces, unidades, UNC, traversal y enlaces.

- Verificación recursiva de submódulos del SDK: revisiones fijadas y archivos
  adicionales, incluidos headers ignorados a varios niveles de profundidad.
- Pruebas del proveedor de cobertura fuera de CI, junto al resto de tooling local.
- SDK nativo verificado frente a archivos adicionales; SDK SourcePawn gestionado
  comparado con el archivo fijado y proveedores externos identificados por sus
  hashes reales, sin atribuirles el lock.
- Documentación de versión fijada, contenido del ZIP y límites de validación
  alineada con el comportamiento actual.

### Cobertura de automatización

- Pruebas de contratos para descarga y reutilización del SDK, revisiones fijadas,
  checkouts modificados, hashes, compilación, exports, metadatos, limpieza por
  plataforma y entorno MSVC. Proveedores externos controlados y archivos temporales.
- Entradas CLI invocables conservando argumentos y directorios predeterminados;
  pruebas adicionales de configuración, secretos y rechazo de análisis incompletos.

### Correcciones de análisis estático

- Eliminada una ruta de includes inexistente del build; el análisis conserva
  las órdenes reales y rechaza errores del scanner aunque su salida sea exitosa.
- Simplificados validadores de paquetes, exports y publicación, sin cambiar sus
  controles; constantes de metadatos centralizadas por consumidor.
- Contexto de compilador dividido por responsabilidad, Python 3.12 explícito y
  cobertura local ampliada a las ejecuciones reales del tooling de análisis.

### Configuración de análisis y lock SourcePawn

- Valores Sonar centralizados en `.env` local y `.env.example`, sin archivo
  `sonar-project.properties`; token separado y recuperación CXX desactivada.
- Lock SourcePawn en `scripts/deps/sourcepawn-package.lock.json`, conservando
  versión y SHA-256; lectores, procedencia de build y caché de CI actualizados.

### Reestructuración de build y distribución

- Make es la interfaz local/CI; scripts por responsabilidad, mapa único y docs
  por funcionalidad. Harnesses fuera de fuentes instalables.
- Artefactos canónicos `l4d2-speedwatch-<canal>-<so>.zip` y extensión con sufijo
  `.ext.2.l4d2`. Actualizar consumidores de URLs y retirar copias antiguas antes
  de instalar; esta edición no instala nada.
- Paquetes validados por contenido, plataforma, hashes y ZIP; publicación con
  borrador y ambos sistemas, separada de la generación local.
- Sonar y cobertura real mediante Make solo localmente, con secretos fuera del
  repositorio. No cambia detector, umbrales, API de BanSystem ni persistencia.

### Mejoras sobre 0.12.0

- Contexto diagnóstico de L4D2 en muestras debug y alertas, con fotografía previa
  a forwards e identidad de ventana nativa. Valores ausentes permanecen desconocidos.
- Drenaje FIFO con cursor y limpieza única; conserva inserciones reentrantes,
  firmas públicas, integración de Demo y marcadores de persistencia de 30 segundos.

No cambia umbrales, movimiento, sanciones ni API pública/nativa. La validación
local no sustituye las pruebas de juego y las mediciones de recursos.
