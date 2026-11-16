/**
 * Logger privado de SpeedWatch. GPL-3.0-or-later.
 * Se incluye desde l4d2_speedwatch.sp; no es un plugin independiente.
 */

/**
 * Un único archivo en append conserva alertas y diagnósticos entre mapas.
 * Las ConVars globales controlan directamente las categorías de debug.
 */
enum struct RuntimeLog
{
    File file;
    bool initTried;
    bool errorLogged;
    bool dirty;
    char path[PLATFORM_MAX_PATH];
    char session[32];
    int evaluation;

    /**
     * Comprueba el directorio de logs de SourceMod y lo crea si falta.
     *
     * @return             True si el directorio existe o se creó correctamente.
     */
    bool bEnsureDirectory()
    {
        char directory[PLATFORM_MAX_PATH];
        BuildPath(Path_SM, directory, sizeof(directory), "logs");
        if (DirExists(directory))
        {
            return true;
        }
        return CreateDirectory(directory, 511);
    }

    /**
     * Abre el log en modo append después de asegurar su directorio.
     * Se intenta una sola vez por carga para evitar errores repetidos.
     */
    void Init()
    {
        if (this.initTried)
        {
            return;
        }
        this.initTried = true;
        Format(this.session, sizeof(this.session), "%08x-%08x-%08x", GetTime(), view_as<int>(GetEngineTime()), view_as<int>(GetMyHandle()));
        BuildPath(Path_SM, this.path, sizeof(this.path), "logs/l4d2_speedwatch.log");
        if (!this.bEnsureDirectory())
        {
            this.Fail("directory");
            return;
        }
        this.file = OpenFile(this.path, "a");
        if (this.file == null)
        {
            this.Fail("open");
        }
    }

    /**
     * Comprueba si una categoría de diagnóstico puede escribir al archivo.
     *
     * @param flag         Bit de la categoría de debug.
     * @return             True si debug, categoría y archivo están disponibles.
     */
    bool bDebug(int flag)
    {
        return this.file != null && g_cvDebug.BoolValue && (g_cvDebugMask.IntValue & flag) != 0;
    }

    /**
     * Añade fecha, categoría y mensaje al archivo mediante buffering.
     * El llamador decide si corresponde un diagnóstico o una alerta obligatoria.
     *
     * @param category     Categoría que identifica el registro.
     * @param message      Mensaje ya formateado.
     */
    void Write(const char[] category, const char[] message)
    {
        if (this.file == null)
        {
            return;
        }
        char timestamp[32];
        FormatTime(timestamp, sizeof(timestamp), "%Y-%m-%d %H:%M:%S");
        if (!this.file.WriteLine("%s [%s] session=%s evaluation=%08x observation_epoch=%d %s",
            timestamp, category, this.session, this.evaluation, g_Runtime.observationGeneration, message))
        {
            this.Fail("write");
            return;
        }
        this.dirty = true;
    }

    /**
     * Vacía el buffer del archivo solamente si existen escrituras pendientes.
     */
    void Flush()
    {
        if (this.file != null && this.dirty)
        {
            if (!this.file.Flush())
            {
                this.Fail("flush");
            }
            this.dirty = false;
        }
    }

    /**
     * Cierra el logger tras un fallo y emite un único error por carga.
     * El detector continúa funcionando aunque el archivo no esté disponible.
     *
     * @param stage        Etapa de la operación que falló.
     */
    void Fail(const char[] stage)
    {
        delete this.file;
        this.dirty        = false;
        if (!this.errorLogged)
        {
            this.errorLogged = true;
            LogError("[SpeedWatch] [logging] event=unavailable stage=%s path=%s", stage, this.path);
        }
    }

    /**
     * Vacía las escrituras pendientes y libera el handle del archivo.
     */
    void Close()
    {
        this.Flush();
        delete this.file;
    }
}

RuntimeLog g_Log;

/**
 * Escribe un diagnóstico solamente si debug y su categoría están habilitados.
 *
 * @param flag         Bit de la categoría que habilita este diagnóstico.
 * @param category     Etiqueta de categoría para el archivo.
 * @param format       Formato del mensaje; los varargs comienzan en posición 4.
 * @param ...          Argumentos para sustituir en el formato.
 */
void DebugLog(int flag, const char[] category, const char[] format, any...)
{
    if (!g_Log.bDebug(flag))
    {
        return;
    }
    char message[768];
    VFormat(message, sizeof(message), format, 4);
    g_Log.Write(category, message);
}

/**
 * Escribe y vacía una alerta sin depender de debug ni de su máscara.
 *
 * @param category     Etiqueta de categoría para el archivo.
 * @param format       Formato del mensaje; los varargs comienzan en posición 3.
 * @param ...          Argumentos para sustituir en el formato.
 */
void DetectionLog(const char[] category, const char[] format, any...)
{
    // Las alertas omiten los filtros de activación y categorías de debug.
    if (g_Log.file == null)
    {
        return;
    }
    char message[768];
    VFormat(message, sizeof(message), format, 3);
    g_Log.Write(category, message);
    g_Log.Flush();
}

/** Same debug gate and vararg indexing as DebugLog; no formatting when disabled. */
void DebugClientLog(int flag, const char[] category, int client, const char[] format, any...)
{
    if (!g_Log.bDebug(flag)) return;
    char message[768], context[128];
    VFormat(message, sizeof(message), format, 5);
    FormatNativeLogContext(client, GetClientUserId(client), context, sizeof(context));
    Format(message, sizeof(message), "%s %s", message, context);
    g_Log.Write(category, message);
}

/** Mandatory alerts retain their existing debug-independent behaviour. */
void DetectionClientLog(int client, const char[] category, const char[] format, any...)
{
    if (g_Log.file == null) return;
    char message[768], context[128];
    VFormat(message, sizeof(message), format, 4);
    FormatNativeLogContext(client, GetClientUserId(client), context, sizeof(context));
    Format(message, sizeof(message), "%s %s", message, context);
    g_Log.Write(category, message);
    g_Log.Flush();
}

/** Context is emitted for any selected active category, including samples-only.
 * Uses local dependency state: never queries provider natives during setup/hooks.
 */
void LogDebugContext(const char[] trigger)
{
    if (g_Log.file == null || !g_cvDebug.BoolValue || (g_cvDebugMask.IntValue & DEBUG_DEFAULT) == 0) return;
    char map[PLATFORM_MAX_PATH] = "unavailable";
    if (g_Runtime.mapLoaded) GetCurrentMap(map, sizeof(map));
    char message[768];
    Format(message, sizeof(message), "event=debug_context trigger=%s version=%s map=%s map_loaded=%d late_load=%d debug=%d flags=%d backend=native signal=run_command_attempts core_available=%d core_pending=%d caps=%d api_expected=%d enabled=%d rate=%.3f burst=%.3f samples=%d grace=%.3f cooldown=%.3f recovery=%.3f public=%d interval=%.6f",
        trigger, SPEEDWATCH_VERSION, map, g_Runtime.mapLoaded, g_Runtime.lateLoad, g_cvDebug.BoolValue, g_cvDebugMask.IntValue,
        g_Runtime.coreAvailable, g_Runtime.coreNeedsSync, g_Runtime.coreCapabilities, SPEEDWATCH_CORE_API_VERSION,
        g_cvEnabled.BoolValue, g_cvRate.FloatValue, g_cvBurst.FloatValue, g_cvSamples.IntValue, g_cvGrace.FloatValue,
        g_cvCooldown.FloatValue, g_cvRecoveryTime.FloatValue, g_cvPublic.BoolValue, GetTickInterval());
    g_Log.Write("general", message);
    g_Log.Flush();
}

/** Logging settings never reset detector history or observation generations. */
public void OnDebugSettingChanged(ConVar convar, const char[] oldValue, const char[] newValue)
{
    LogDebugContext("debug_setting");
}
