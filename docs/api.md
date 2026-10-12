# API pública y consumidores

[Índice de documentación](index.md) · [README](../README.md)

Include: `addons/sourcemod/scripting/include/l4d2_speedwatch.inc`.
Biblioteca: `l4d2_speedwatch`.
El proveedor registra su API en `AskPluginLoad2` y acepta consumidores obligatorios
u opcionales. Copiar el include al SDK del consumidor para compilarlo.

## Forward de alertas

```sourcepawn
#include <l4d2_speedwatch>

public void SpeedWatch_OnDetection(int client, int accountId, int userId,
    float commandsPerSecond, float ratio, float excess, int consecutiveSamples)
{
    // Los valores describen la muestra original, aunque el jugador ya haya salido.
    PrintToServer("SpeedWatch: client=%d accountid=%d userid=%d ratio=%.3f",
        client, accountId, userId, ratio);
}
```

El forward se emite una vez por alerta, después del log y el chat, respetando
el cooldown. No se emite para sospechas intermedias y no permite cancelar la alerta.
No depende de las ConVars de debug ni del éxito del archivo de log. Entrega una
copia de las métricas anteriores a cualquier cambio que haga un consumidor.

`client` es el slot de la conexión al producirse la alerta. `accountId` es el
Steam AccountID de 32 bits validado, no SteamID64. Si la identidad aún no está
validada, vale `0`; no usar `0` como identidad persistente. `userId` identifica la
conexión original: antes de actuar sobre el slot, comprobar que
`GetClientOfUserId(userId) == client` y que sigue en juego. Otro consumidor podría
haber desconectado al jugador; para trabajo diferido conservar los valores de
identidad y revalidar la conexión antes de usar APIs de cliente.

## Forward de estados

`SpeedWatch_OnDetectionStateChanged(client, accountId, userId, state, reason)`
comunica el inicio y cierre de episodios sin depender del cooldown del chat.
El contrato completo, los estados y el ejemplo para un grabador están en
[episodios y grabación](recording.md).

## Consulta de muestras

```sourcepawn
native bool SpeedWatch_GetClientSample(int client, SpeedWatchSample sample);
```

`SpeedWatch_GetClientSample` copia la última muestra al struct del include:
`client`, `accountId`, `userId`, `engineTime`, `commandsPerSecond`, `ratio`,
`excess`, `consecutiveSamples` e `inGrace`. Incluye muestras recogidas durante
gracia; `engineTime` es el reloj `GetEngineTime()`, no una fecha Unix. La identidad
corresponde al instante de evaluación; una muestra con AccountID `0` puede
preceder a la validación de Steam de esa conexión.

Devuelve `false` y pone la salida a cero si no hay muestra vigente: mapa no disponible, cierre de observación, pausa,
readyup, sincronización pendiente, detector desactivado, muestra global inválida, más de
2 segundos de antigüedad, muerte, desconexión, bots, espectadores o reinicio del
historial. Un índice fuera de `1..MaxClients` genera error de native. Una muestra
devuelta es una copia; el consumidor no modifica el estado interno del detector.
Las lecturas no acumulan exceso ni emiten alertas.

Ejemplo de consulta dentro de una función del consumidor:

```sourcepawn
void ShowSpeedSample(int client)
{
    SpeedWatchSample sample;
    if (SpeedWatch_GetClientSample(client, sample))
    {
        PrintToServer("accountid=%d cmds/s=%.2f grace=%d",
            sample.accountId, sample.commandsPerSecond, sample.inGrace);
    }
}
```

## Dependencia opcional y compatibilidad

Para una dependencia opcional, usar `#undef REQUIRE_PLUGIN` antes del include
y restaurarlo después. Antes de invocar el native, comprobar
`LibraryExists("l4d2_speedwatch")` desde un punto seguro de uso: la biblioteca
garantiza el native de consulta. Las altas/bajas de biblioteca solo deben
actualizar disponibilidad local. Compilar los consumidores con el include
correspondiente al proveedor; los cambios de firmas o estructura requieren
revisar y recompilar los consumidores. Los consumidores anteriores que consultan
la versión de API deben eliminar esa llamada y recompilarse.

La API no añade consultas de identidad ni forwards a `OnPlayerRunCmdPre`.
La copia para consumidores se actualiza en el timer existente. El forward original
se invoca por alerta; el nuevo forward de estado, únicamente por transición del episodio. Un consumidor lento sí puede
añadir coste al ejecutarse su callback en el hilo del servidor.

## Consumidor de diagnóstico

El ejemplo de diagnóstico `addons/sourcemod/scripting/l4d2_speedwatch_test.sp` es un consumidor
real del include y se conserva solo en el checkout de desarrollo. No se compila
en CI ni se incluye en el paquete de producción. Compilar ambos modos (opcional y obligatorio) con:

```bash
make build-api-test
```

Los SMX de prueba quedan en `.build/tests/` y no se incluyen en
`addons/sourcemod/plugins/` del paquete. Para probarlo expresamente en SRCDS,
instalar solo el consumidor opcional junto con el proveedor y ejecutar
`sm_speedwatch_api_test` desde consola o con permiso root. Comprueba
identidad de conexión y salida a cero cuando no hay muestra. También verifica
orden, motivo e identidad de las transiciones que observa; tolera recibir solo
un terminal si se carga durante un episodio. Recibe las alertas
reales por forward; no simula speedhack ni dispara alertas artificiales.

Los escenarios de prueba de API y callbacks están en [validación](testing.md).
