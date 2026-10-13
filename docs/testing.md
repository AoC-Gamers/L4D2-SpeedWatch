# Validación y pruebas en SRCDS

[Índice de documentación](index.md) · [README](../README.md)

## Evidencia local y alcance

Validado localmente: compilación con SourcePawn 1.12.0.7255 y `-E`, sin warnings;
metadatos del SMX con `pause`, `readyup` y `left4dhooks` marcados `required=0` e inicializadores
de natives opcionales exportados. API y consumidores opcional/obligatorio compilados con `-E`;
contrato de dependencia e imports/exports verificados en los metadatos SMX.
La división en tres módulos privados conserva los bloques originales y compila
con el mismo compilador y `-E`. Se comprueba que el ZIP contiene los tres módulos
y un único SMX de producción, excluye el test, los includes de terceros y la
documentación (`docs/` y `README.md`). La licencia y el log de compilación se conservan.
La recompilación completa usa las fuentes e includes del checkout junto con el SDK.
Revisión estática: callbacks de biblioteca pasivos, ausencia
de consultas a `IsInPause()` en la ruta por comando y registro de alertas sin
condición de debug o máscara. Readyup usa la presencia de su biblioteca como garantía de su native;
conteo, evaluación y consulta pública excluyen readyup y sincronización pendiente.
Pendiente: carga en SRCDS, traducciones en chat, detección real, falsos positivos,
coste de CPU, integración opcional de pausa, ConVars de debug, creación/append del log en SRCDS, fallo de permisos
y comportamiento en todos los modos. La compilación no demuestra
ninguno de esos resultados runtime.

## Detector y coste de CPU

Procedimiento de validación del detector:

1. Cargar en un servidor de pruebas y consultar status con humanos a cadencia
   normal, a los tickrates que realmente utilice el servidor.
2. Observar conexión, muerte/respawn, cambio de equipo, takeover de bot,
   transición de mapa, restart y las mitades de Versus/Scavenge.
3. Probar jitter, pérdida de paquetes y recuperación de ráfagas; revisar si
   acumulan exceso o producen alertas espurias.
4. Probar pausa/unpause y retrasos del servidor; confirmar descarte y gracia.
5. Con tráfico de exceso controlado en pruebas, confirmar que la sospecha aparece
   con la racha requerida y que el cooldown evita repeticiones frecuentes.
6. Comprobar chat admin/público, idioma y permisos, y que el plugin no bloquea
   ningún comando ni modifica movimiento.
7. Comparar CPU de forma repetida bajo la misma carga de humanos, bots, mapa,
   tickrate y plugins: sin detector, con SpeedWatch y con el módulo SMAC.
   Comparar primero el módulo aislado; el total de una suite no atribuye costes
   a un detector. Usar el profiler disponible y frame times además del CPU total.

Usar estas mediciones para ajustar los umbrales y documentar los falsos positivos
y el coste de CPU observados.

## Logs y debug

Pendiente en SRCDS: cargar con `logs/` disponible
y con directorio ausente en una instalación de prueba; activar debug y probar
cada bit por separado, `12`, `15`, `31`, `0` y modo normal. Confirmar la
ausencia de líneas de diagnóstico con debug en `0` y que cada cambio de debug o
flags se aplique en la siguiente comprobación, sin recargar el plugin.
Generar una alerta con debug y flags en `0` y verificar que queda en el archivo;
recargar y
comprobar append. Probar un destino sin permisos y verificar `file_ready=0`,
un solo error y continuidad del detector. No se han ejecutado estas pruebas
runtime en este cambio.

## Pause

Pendiente en SRCDS: cargar SpeedWatch sin `pause.smx`; cargar
ambos y pausar/reanudar; cargar SpeedWatch mientras ya existe una pausa; cargar
el proveedor después; descargar y recargar `pause` con partida activa y durante
pausa. Verificar ausencia de errores de native, conteo suspendido, descarte del
historial, gracia y continuidad del log obligatorio de alertas. Probar una pausa
corta entre evaluaciones, el countdown de unpause y cambio de mapa/ronda estando
pausado. Descargar el proveedor no obliga al motor a reanudar: SpeedWatch sigue
aplicando sus comprobaciones generales de simulación cuando no hay proveedor.

## Readyup

Validación en SRCDS pendiente: sin readyup; readyup presente pero desactivado;
cargar SpeedWatch durante preparación; cargar/descargar readyup durante live y
preparación; cuenta regresiva y cancelación; transición a live; segunda mitad,
restart y cambio de mapa; pausa durante readyup y live. Consultar status/API,
verificar descarte de muestras y reanudación con gracia, sin errores de native
opcional ni alertas de muestras recogidas durante preparación.

## Cierre de observación y modos

Pendiente en SRCDS:

- Terminar una mitad de Versus, una mitad/match de Scavenge y un intento Coop
  por fallo, transición o finale. Antes de `OnMapEnd`, comprobar
  `map_loaded=1`, `observation_ended=1`, `valid_sample=0` y salida de API a cero.
- Repetir una señal de fin; confirmar que no vuelve a contar ni conserva deuda.
  Probar también el orden de eventos genéricos y específicos al cambiar de mitad.
- Con la observación cerrada, reanudar pausa, salir de readyup y cambiar una regla;
  ninguno debe reabrirla. En la siguiente ronda, confirmar sincronización y gracia.
- Cambiar mapa o reiniciarlo administrativamente; confirmar que no hay muestras
  anteriores y que el nuevo mapa puede observarse. Incluir una señal de ronda
  anterior a `OnMapStart` para comprobar que ese callback no elimina un cierre.
- Cargar tarde con partida activa y durante readyup/pausa; confirmar exclusiones
  y gracia. La prueba no debe interpretar eventos anteriores a la carga como
  señales recibidas por SpeedWatch.
- Emitir un evento de fin desde un consumidor de `SpeedWatch_OnDetection`;
  confirmar que se detiene el resto de esa evaluación y que la API queda inválida.

La versión 0.8.0 y ambos consumidores compilaron con `-E` sin warnings. La revisión
estática conserva los handlers/reconciliadores de pause y readyup, el cálculo del
detector y el registro obligatorio de alertas. Estas comprobaciones no sustituyen
la matriz de runtime anterior.

## Left4DHooks

Pendiente en SRCDS: cargar sin proveedor y confirmar
el respaldo `round_end`; con proveedor y modo `2`, comprobar que se ignora ese
evento y que el forward cierra la mitad. Probar un cierre bloqueado por otro
plugin, modo desconocido, Coop/Survival/Scavenge, cambio de modo, carga tardía
con escaneo de detours, alta/baja/recarga del proveedor y cambio de mapa. Repetir
con pausa y readyup activos: la sincronización de modo no debe habilitar el
conteo ni la API durante sus exclusiones. El log obligatorio de alertas y las
firmas públicas anteriores de SpeedWatch permanecen iguales.

## API pública

Pendiente en SRCDS: sin proveedor, carga tardía, carga/descarga del proveedor,
conexión/desconexión y reutilización de slot, identidad aún no validada, muestras
en gracia, pausa/reanudación y detecciones reales con debug apagado. Comparar
los valores del forward con el registro `event=alert`, que ahora incluye también
`client` y `accountid`. Verificar que un consumidor que pause o cambie las reglas
durante el forward interrumpe el resto de esa evaluación.

El consumidor de diagnóstico se compila e instala según [API pública](api.md#consumidor-de-diagnóstico).

## Episodios y grabación

Pendiente en SRCDS:

1. Completar el umbral: un único `Active` aunque continúe el exceso y haya varias
   alertas; ambos forwards deben llevar la identidad de la misma conexión.
2. Tras cuatro segundos válidos normales, introducir exceso o cero comandos:
   no debe recuperar; completar luego al menos cinco segundos normales para un
   único `Recovered` con `NormalCadence`. No recuperar durante gracia.
3. Abrir un nuevo episodio antes de vencer el cooldown: debe emitir `Active`
   aunque se suprima el chat. Probar también recuperación con deuda remanente.
4. Durante un episodio, probar pausa, readyup, muerte, cambio de equipo,
   desconexión/reutilización de slot, cierre/inicio de ronda/mapa, desactivación,
   cambio de reglas, tiempos irregulares, timescale y cambio de proveedor/modo.
   Esperar un solo `Interrupted` con identidad original y motivo correspondiente,
   nunca `Recovered`. Tras la gracia, un nuevo episodio requiere su umbral.
5. Descargar SpeedWatch con un episodio activo: esperar `Interrupted` con
   `PluginUnloaded`. Cargar tarde el consumidor y verificar que tolera un terminal
   sin inicio observado; retirar/recargar el proveedor no debe generar errores.
6. Usar dos consumidores: hacer que el primero pause o desconecte desde `Active`.
   Ambos deben recibir `Active` y después `Interrupted`, sin alerta obsoleta ni
   continuación del timer con contexto invalidado. Repetir con cambio de reglas
   desde un terminal y con varios sospechosos activos.
7. Con debug y flags en cero, comprobar en el log cada `detection_state`, incluso
   los inicios durante cooldown. Probar dos episodios simultáneos y una nueva
   detección durante la cola del grabador antes de integrar la parada real.

La compilación y la revisión estática de 0.8.0 están completas. Esta matriz de
comportamiento y el coste real de CPU siguen pendientes en SRCDS.

## Cadena de build y empaquetado

El workflow y los targets se describen en [build y CI/CD](build-system.md).
`make test-ci` usa un compilador espía en proyectos temporales para verificar
selección de entrypoints, limpieza de binarios antiguos, payload del ZIP,
rechazo de SMX ajenos y propagación de fallos de compilación. Esas pruebas de
orquestación no sustituyen una compilación real de SourcePawn ni una prueba en SRCDS.

Validación local del pipeline: cinco pruebas aprobadas, incluyendo exclusión
y rechazo de documentación en el artefacto,
compilación real de `l4d2_speedwatch.sp` con SourcePawn 1.12.0.7255 y `-E` sin
warnings, staging validado y release ZIP con un único SMX de producción.
También se verificó un build real en un directorio temporal con una fuente de
test deliberadamente inválida: compiló únicamente producción. Otro directorio,
sin SDK y con el build/log recibidos, generó la release conservando ese SMX y
excluyendo el test. La resolución de canales se comprobó para main, develop y PR,
y el workflow pasó la validación local con actionlint 1.7.12.
El test de SourcePawn permanece fuera del build automático. Los resultados
remotos de cada commit y la publicación de canales se consultan en
[GitHub Actions](https://github.com/AoC-Gamers/L4D2-SpeedWatch/actions/workflows/sourcemod-build.yml).
Las comprobaciones anteriores describen evidencia local y no sustituyen el
resultado remoto ni las pruebas en SRCDS.
