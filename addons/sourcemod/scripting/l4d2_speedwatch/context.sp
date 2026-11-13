/**
 * Contexto diagnóstico de L4D2. GPL-3.0-or-later.
 * Incluido por detector.sp. No modifica comandos, umbrales ni movimiento.
 * Las estructuras son locales a una evaluación: no hay historial por jugador.
 */

enum struct MovementProfile
{
    char mode[64];
    int survivors;
    int infected;
    int survivorLimit;
    int infectedLimit;
    int antiBhopEnabled;
    int survivorBhopAllowed;
    int infectedBhopFlags;
}

enum struct MovementContext
{
    bool captured;
    int client;
    int userId;
    float sampleTime;
    int serverTick;
    int team;
    int zombieClass;
    int grounded;
    int ducked;
    int waterLevel;
    int moveType;
    int ghost;
    int incapacitated;
    int hanging;
    int adrenaline;
    int pinned;
    int health;
    float healthBufferRaw;
    float speed2d;
    float maxspeedProperty;
    int bhopConfig;
}

/** No exige equipos completos, simetría ni un número fijo de participantes. */
bool IsPlayingTeam(int team)
{
    return team == 2 || team == 3;
}

/** -1 significa que la ConVar no está disponible, no un valor predeterminado. */
int ContextConVarInt(const char[] name)
{
    ConVar value = FindConVar(name);
    return value == null ? -1 : value.IntValue;
}

/** Una captura compartida por evaluación, solo si se va a escribir contexto. */
void CaptureMovementProfile(MovementProfile profile)
{
    strcopy(profile.mode, sizeof(profile.mode), "unknown");
    ConVar mode = FindConVar("mp_gamemode");
    if (mode != null)
    {
        mode.GetString(profile.mode, sizeof(profile.mode));
    }
    profile.survivors = 0;
    profile.infected = 0;
    for (int client = 1; client <= MaxClients; client++)
    {
        if (!g_bHuman[client] || !IsClientInGame(client))
        {
            continue;
        }
        // Cuenta integrantes humanos, también muertos/fantasmas, no espectadores.
        int team = GetClientTeam(client);
        if (team == 2)
        {
            profile.survivors++;
        }
        else if (team == 3)
        {
            profile.infected++;
        }
    }
    // Son metadatos de configuración, nunca límites para recorrer slots.
    profile.survivorLimit = ContextConVarInt("survivor_limit");
    profile.infectedLimit = ContextConVarInt("z_max_player_zombies");
    profile.antiBhopEnabled = ContextConVarInt("simple_antibhop_enable");
    profile.survivorBhopAllowed = ContextConVarInt("bhop_allow_survivor");
    profile.infectedBhopFlags = ContextConVarInt("bhop_except_si_flags");
}

/** Configuración declarada: -1 desconocida, 0 desactivada, 1 restringida, 2 exenta.
 * La existencia de ConVars NO prueba que el plugin anti-bhop siga cargado.
 */
int ConfiguredBhopPolicy(int team, int zombieClass, MovementProfile profile)
{
    if (profile.antiBhopEnabled < 0)
    {
        return -1;
    }
    if (profile.antiBhopEnabled == 0)
    {
        return 0;
    }
    if (team == 2)
    {
        if (profile.survivorBhopAllowed < 0)
        {
            return -1;
        }
        return profile.survivorBhopAllowed != 0 ? 2 : 1;
    }
    if (team != 3 || profile.infectedBhopFlags < 0)
    {
        return -1;
    }
    int bit = -1;
    if (zombieClass >= 1 && zombieClass <= 6)
    {
        bit = zombieClass - 1;
    }
    else if (zombieClass == 8)
    {
        bit = 6; // Tank; Witch (7) no representa un jugador especial válido.
    }
    if (bit < 0)
    {
        return -1;
    }
    return (profile.infectedBhopFlags & (1 << bit)) != 0 ? 2 : 1;
}

int ContextSendInt(int client, const char[] property)
{
    return HasEntProp(client, Prop_Send, property)
        ? GetEntProp(client, Prop_Send, property) : -1;
}

bool ContextFinite(float value)
{
    return (view_as<int>(value) & 0x7f800000) != 0x7f800000;
}

float ContextFloat(int client, PropType type, const char[] property)
{
    if (!HasEntProp(client, type, property))
    {
        return -1.0;
    }
    float value = GetEntPropFloat(client, type, property);
    return ContextFinite(value) && value >= 0.0 ? value : -1.0;
}

/** Solo inmovilización por SI; no pretende cubrir empujones ni toda fuerza externa. */
int ContextPinState(int client)
{
    static const char properties[][] =
    {
        "m_tongueOwner", "m_pounceAttacker", "m_jockeyAttacker",
        "m_carryAttacker", "m_pummelAttacker"
    };
    bool complete = true;
    for (int i = 0; i < sizeof(properties); i++)
    {
        if (!HasEntProp(client, Prop_Send, properties[i]))
        {
            complete = false;
        }
        else if (GetEntPropEnt(client, Prop_Send, properties[i]) > 0)
        {
            return 1;
        }
    }
    return complete ? 0 : -1;
}

/** Fotografía al evaluar; no es media/pico de la ventana ni prueba de simulación. */
void CaptureMovementContext(int client, float now, MovementProfile profile, MovementContext context)
{
    context.captured = false;
    if (!g_bHuman[client] || !IsClientInGame(client) || !IsPlayerAlive(client)
        || !IsPlayingTeam(GetClientTeam(client)))
    {
        return;
    }
    context.client = client;
    context.userId = GetClientUserId(client);
    context.sampleTime = now;
    context.serverTick = GetGameTickCount();
    context.team = GetClientTeam(client);
    context.zombieClass = context.team == 3 ? ContextSendInt(client, "m_zombieClass") : 0;
    int flags = GetEntityFlags(client);
    context.grounded = (flags & FL_ONGROUND) != 0 ? 1 : 0;
    context.ducked = (flags & FL_DUCKING) != 0 ? 1 : 0;
    context.waterLevel = ContextSendInt(client, "m_nWaterLevel");
    context.moveType = view_as<int>(GetEntityMoveType(client));
    context.ghost = context.team == 3 ? ContextSendInt(client, "m_isGhost") : 0;
    context.incapacitated = context.team == 2 ? ContextSendInt(client, "m_isIncapacitated") : -1;
    context.hanging = context.team == 2 ? ContextSendInt(client, "m_isHangingFromLedge") : -1;
    context.adrenaline = context.team == 2 ? ContextSendInt(client, "m_bAdrenalineActive") : -1;
    context.pinned = context.team == 2 ? ContextPinState(client) : -1;
    context.health = GetClientHealth(client);
    // El buffer bruto no equivale a salud temporal restante ni salud efectiva.
    context.healthBufferRaw = context.team == 2
        ? ContextFloat(client, Prop_Send, "m_healthBuffer") : -1.0;
    // Esta propiedad es una referencia observada, NO un techo físico universal.
    context.maxspeedProperty = ContextFloat(client, Prop_Data, "m_flMaxspeed");
    context.speed2d = -1.0;
    if (HasEntProp(client, Prop_Data, "m_vecAbsVelocity"))
    {
        float velocity[3];
        GetEntPropVector(client, Prop_Data, "m_vecAbsVelocity", velocity);
        float squared = velocity[0] * velocity[0] + velocity[1] * velocity[1];
        if (ContextFinite(squared) && squared >= 0.0)
        {
            context.speed2d = SquareRoot(squared);
        }
    }
    context.bhopConfig = ConfiguredBhopPolicy(context.team, context.zombieClass, profile);
    context.captured = true;
}

/** Escribe una copia tomada antes de los forwards; nunca reconsulta al sospechoso. */
void WriteMovementContext(MovementContext context, MovementProfile profile, bool alert)
{
    if (!context.captured || g_Log.file == null || (!alert && !g_Log.bDebug(DEBUG_SAMPLES)))
    {
        return;
    }
    char message[768];
    Format(message, sizeof(message),
        "event=movement_context schema=1 scope=sample_end source=%s slot=%d userid=%d time=%.3f server_tick=%d mode=%s humans_survivor=%d humans_infected=%d survivor_limit=%d infected_limit=%d team=%d class=%d ground=%d duck=%d water=%d movetype=%d ghost=%d incap=%d hanging=%d adrenaline=%d pinned=%d health=%d health_buffer_raw=%.2f speed2d=%.2f maxspeed_prop=%.2f bhop_config=%d",
        alert ? "alert" : "sample", context.client, context.userId, context.sampleTime,
        context.serverTick, profile.mode, profile.survivors, profile.infected,
        profile.survivorLimit, profile.infectedLimit, context.team, context.zombieClass,
        context.grounded, context.ducked, context.waterLevel, context.moveType,
        context.ghost, context.incapacitated, context.hanging, context.adrenaline,
        context.pinned, context.health, context.healthBufferRaw, context.speed2d,
        context.maxspeedProperty, context.bhopConfig);
    g_Log.Write("context", message);
    if (alert)
    {
        g_Log.Flush();
    }
}
