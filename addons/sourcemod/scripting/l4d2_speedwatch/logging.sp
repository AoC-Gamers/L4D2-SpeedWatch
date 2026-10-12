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
        if (!this.file.WriteLine("%s [%s] %s", timestamp, category, message))
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
