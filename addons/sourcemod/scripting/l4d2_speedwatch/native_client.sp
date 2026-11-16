/** A read-only copy. Repeated queries never advance the per-rule cursor. */
bool ReadNativeObservation(int client, int[] sample)
{
    return SpeedWatchCore_GetSample(client, sample, SPEEDWATCH_CORE_SAMPLE_CELLS);
}

/** Native windows are the sole input to the command-cadence detector. */
#define NATIVE_DETECTOR_CAPS (SPEEDWATCH_CORE_CAP_BLOCKS | SPEEDWATCH_CORE_CAP_RUN_ATTEMPTS | SPEEDWATCH_CORE_CAP_TEAM)
// Diagnostic bits; these describe existing rejection rules, not new thresholds.
#define WINDOW_HEADER          (1 << 0)
#define WINDOW_IDENTITY        (1 << 1)
#define WINDOW_EPOCH           (1 << 2)
#define WINDOW_TEAM            (1 << 3)
#define WINDOW_CAPABILITIES    (1 << 4)
#define WINDOW_TIMING          (1 << 5)
#define WINDOW_COUNTER         (1 << 6)
#define WINDOW_FIRST           (1 << 7)
#define WINDOW_GENERATION      (1 << 8)
#define WINDOW_DUPLICATE       (1 << 9)
#define WINDOW_GAP             (1 << 10)
#define WINDOW_QUALITY         (1 << 11)
// Bit 12 retired: dropped_packets is diagnostic metadata, not a rejection reason.
#define WINDOW_IGNORED         (1 << 13)
#define WINDOW_PAUSED          (1 << 14)
#define WINDOW_CORE_NOT_READY  (1 << 15)
#define WINDOW_UNAVAILABLE     (1 << 16)
#define WINDOW_INSTANCE        (1 << 17)
#define WINDOW_INVALID_FIELDS (WINDOW_HEADER | WINDOW_IDENTITY | WINDOW_EPOCH | WINDOW_TEAM | WINDOW_CAPABILITIES | WINDOW_TIMING | WINDOW_COUNTER)
NativeObservationState g_CoreStates[MAXPLAYERS + 1];
bool g_CoreWindowReady[MAXPLAYERS + 1];
bool g_CoreHasSample[MAXPLAYERS + 1];
int g_CoreSamples[MAXPLAYERS + 1][SPEEDWATCH_CORE_SAMPLE_CELLS];

bool bNativeDetectorReady()
{
    return g_Runtime.coreAvailable && g_Runtime.coreControllerAvailable && !g_Runtime.coreNeedsSync
        && (g_Runtime.coreCapabilities & NATIVE_DETECTOR_CAPS) == NATIVE_DETECTOR_CAPS;
}

void ReconcileNativeCore()
{
    if (g_Runtime.coreAvailable && !g_Runtime.coreNeedsSync
        && (SpeedWatchCore_GetCapabilities() != g_Runtime.coreCapabilities
            || (SpeedWatchCore_GetStatus(3) != 2) != g_Runtime.coreControllerAvailable))
        g_Runtime.coreNeedsSync = true;
    if (!g_Runtime.coreNeedsSync)
    {
        return;
    }
    bool previouslyAvailable = g_Runtime.coreAvailable;
    g_Runtime.coreNeedsSync = false;
    g_Runtime.coreAvailable = LibraryExists("l4d2_speedwatch_core");
    g_Runtime.coreCapabilities = 0;
    g_Runtime.coreControllerAvailable = false;
    if (g_Runtime.coreAvailable)
    {
        g_Runtime.coreAvailable = SpeedWatchCore_GetApiVersion() == SPEEDWATCH_CORE_API_VERSION;
        if (g_Runtime.coreAvailable)
        {
            g_Runtime.coreCapabilities = SpeedWatchCore_GetCapabilities();
            g_Runtime.coreControllerAvailable = SpeedWatchCore_GetStatus(3) != 2;
        }
    }
    ResetAll(GetEngineTime(), "native_core_sync", SpeedWatchReason_DependencyChanged);
    if (!bNativeDetectorReady())
        DetectionLog("lifecycle", "event=native_detector_unavailable api_expected=%d available=%d caps=%d required=%d controller_available=%d",
            SPEEDWATCH_CORE_API_VERSION, g_Runtime.coreAvailable, g_Runtime.coreCapabilities, NATIVE_DETECTOR_CAPS, g_Runtime.coreControllerAvailable);
    DebugLog(DEBUG_GENERAL, "general", "event=native_core_sync available=%d previous=%d capabilities=%d detection_backend=native",
        g_Runtime.coreAvailable, previouslyAvailable, g_Runtime.coreCapabilities);
    LogDebugContext("core_sync");
}

void PulseNativeCore(bool enabled)
{
    if (g_Runtime.coreAvailable && g_Runtime.coreControllerAvailable)
    {
        SpeedWatchCore_Pulse(enabled && bNativeDetectorReady(), g_Runtime.observationGeneration);
    }
}

void SetNativeParticipant(int client, bool enabled)
{
    if (!enabled)
    {
        g_CoreHasSample[client] = false;
        g_CoreWindowReady[client] = false;
        g_CoreStates[client] = NativeObservation_Absent;
    }
    if (g_Runtime.coreAvailable && g_Runtime.coreControllerAvailable)
    {
        SpeedWatchCore_SetParticipant(client, enabled && bNativeDetectorReady());
    }
}

/** Validate wire evidence before converting any uint64 to a signed SP count.
 * The previous end must equal this start: missing/duplicate windows or a new
 * participant generation interrupt the cadence history. A first window only
 * primes the cursor. Bad quality also interrupts; it never proves recovery.
 * Kept independent of engine calls for isolated tests of the production policy.
 */
int NativeWindowRejectReasons(int client, const int[] sample, int userId, int serial, int team, int epoch)
{
    int reasons = 0;
    float duration = view_as<float>(sample[CoreCell_Duration]);
    float interval = view_as<float>(sample[CoreCell_Interval]);
    if (sample[CoreCell_Api] != SPEEDWATCH_CORE_API_VERSION || sample[CoreCell_Length] != SPEEDWATCH_CORE_SAMPLE_CELLS || sample[CoreCell_Source] != 1)
        reasons |= WINDOW_HEADER;
    if (sample[CoreCell_UserId] != userId || sample[CoreCell_Serial] != serial) reasons |= WINDOW_IDENTITY;
    if (sample[CoreCell_Epoch] != epoch) reasons |= WINDOW_EPOCH;
    if (sample[CoreCell_Team] != team) reasons |= WINDOW_TEAM;
    if ((sample[CoreCell_Capabilities] & NATIVE_DETECTOR_CAPS) != NATIVE_DETECTOR_CAPS) reasons |= WINDOW_CAPABILITIES;
    if (!(duration >= SPEEDWATCH_WINDOW_MIN_SECONDS && duration <= SPEEDWATCH_WINDOW_MAX_SECONDS && interval >= 0.001 && interval <= 1.0)) reasons |= WINDOW_TIMING;
    if (sample[CoreCell_AttemptsLow] < 0 || sample[CoreCell_AttemptsHigh] != 0) reasons |= WINDOW_COUNTER;
    if (!g_CoreWindowReady[client]) reasons |= WINDOW_FIRST;
    else
    {
        if (sample[CoreCell_Generation] != g_CoreSamples[client][CoreCell_Generation]) reasons |= WINDOW_GENERATION;
        if (sample[CoreCell_InstanceLow] != g_CoreSamples[client][CoreCell_InstanceLow] || sample[CoreCell_InstanceHigh] != g_CoreSamples[client][CoreCell_InstanceHigh]) reasons |= WINDOW_INSTANCE;
        if (sample[CoreCell_SampleLow] == g_CoreSamples[client][CoreCell_SampleLow] && sample[CoreCell_SampleHigh] == g_CoreSamples[client][CoreCell_SampleHigh]) reasons |= WINDOW_DUPLICATE;
        if (sample[CoreCell_StartLow] != g_CoreSamples[client][CoreCell_EndLow] || sample[CoreCell_StartHigh] != g_CoreSamples[client][CoreCell_EndHigh]) reasons |= WINDOW_GAP;
    }
    int quality = sample[CoreCell_Quality];
    // Cadence needs attempt counts AND block pause/ignore guards. Physical groups
    // are not required. Unknown quality bits must never become usable evidence.
    int requiredQuality = SPEEDWATCH_QUALITY_TIMING | SPEEDWATCH_QUALITY_BLOCKS | SPEEDWATCH_QUALITY_ATTEMPTS;
    if (sample[CoreCell_State] != view_as<int>(NativeObservation_Published)
        || (quality & requiredQuality) != 0 || (quality & ~SPEEDWATCH_QUALITY_KNOWN) != 0) reasons |= WINDOW_QUALITY;
    // Packet-loss metadata does not invalidate cadence evidence. Legitimate
    // catch-up bursts still pass through the existing buffer and consecutive-sample rule.
    if (sample[CoreCell_IgnoredLow] != 0 || sample[CoreCell_IgnoredHigh] != 0) reasons |= WINDOW_IGNORED;
    if (sample[CoreCell_PausedLow] != 0 || sample[CoreCell_PausedHigh] != 0) reasons |= WINDOW_PAUSED;
    return reasons;
}

bool bAcceptNativeWindow(int client, const int[] sample, int userId, int serial, int team, int epoch)
{
    int reasons = NativeWindowRejectReasons(client, sample, userId, serial, team, epoch);
    g_CoreStates[client] = eNativeObservationState(reasons);
    if ((reasons & WINDOW_INVALID_FIELDS) != 0)
    {
        g_CoreWindowReady[client] = false;
        g_CoreHasSample[client] = false;
        return false;
    }
    for (int i = 0; i < SPEEDWATCH_CORE_SAMPLE_CELLS; i++)
    {
        g_CoreSamples[client][i] = sample[i];
    }
    g_CoreWindowReady[client] = true;
    g_CoreHasSample[client] = true;
    return reasons == 0;
}

void FormatWindowReasons(int reasons, char[] text, int length)
{
    text[0] = '\0';
    if (reasons == 0) { strcopy(text, length, "none"); return; }
    if (reasons & WINDOW_HEADER) StrCat(text, length, "header|");
    if (reasons & WINDOW_IDENTITY) StrCat(text, length, "identity|");
    if (reasons & WINDOW_EPOCH) StrCat(text, length, "epoch|");
    if (reasons & WINDOW_TEAM) StrCat(text, length, "team|");
    if (reasons & WINDOW_CAPABILITIES) StrCat(text, length, "capabilities|");
    if (reasons & WINDOW_TIMING) StrCat(text, length, "timing|");
    if (reasons & WINDOW_COUNTER) StrCat(text, length, "counter_range|");
    if (reasons & WINDOW_FIRST) StrCat(text, length, "first_window|");
    if (reasons & WINDOW_GENERATION) StrCat(text, length, "generation_changed|");
    if (reasons & WINDOW_DUPLICATE) StrCat(text, length, "duplicate|");
    if (reasons & WINDOW_GAP) StrCat(text, length, "discontinuity|");
    if (reasons & WINDOW_QUALITY) StrCat(text, length, "quality|");
    if (reasons & WINDOW_IGNORED) StrCat(text, length, "ignored_blocks|");
    if (reasons & WINDOW_PAUSED) StrCat(text, length, "paused_blocks|");
    if (reasons & WINDOW_CORE_NOT_READY) StrCat(text, length, "core_not_ready|");
    if (reasons & WINDOW_INSTANCE) StrCat(text, length, "core_instance_changed|");
    if (reasons & WINDOW_UNAVAILABLE) StrCat(text, length, "sample_unavailable|");
    int last = strlen(text) - 1;
    if (last >= 0) text[last] = '\0';
}

/** Trace before the validator advances its cursor; IDs are high:low hex bit patterns. */
void LogNativeWindow(int client, const int[] sample, bool available, int reasons)
{
    if (!g_Log.bDebug(DEBUG_SAMPLES)) return;
    char names[320];
    FormatWindowReasons(reasons, names, sizeof(names));
    if (!available)
    {
        DebugLog(DEBUG_SAMPLES, "samples", "event=native_window slot=%d userid=%d window_available=0 accepted=0 reasons=%s reason_bits=%x observation_state=%d",
            client, GetClientUserId(client), names, reasons, g_CoreStates[client]);
        return;
    }
    DebugLog(DEBUG_SAMPLES, "samples", "event=native_window slot=%d userid=%d sample_userid=%d window_available=1 window_epoch=%d generation=%d window=%08x:%08x previous_available=%d previous_window=%08x:%08x accepted=%d reasons=%s reason_bits=%x caps=%d quality=%d attempts=%08x:%08x dropped=%08x:%08x ignored=%08x:%08x paused=%08x:%08x duration=%.3f interval=%.6f",
        client, GetClientUserId(client), sample[CoreCell_UserId], sample[CoreCell_Epoch], sample[CoreCell_Generation], sample[CoreCell_SampleHigh], sample[CoreCell_SampleLow],
        g_CoreWindowReady[client], g_CoreSamples[client][CoreCell_SampleHigh], g_CoreSamples[client][CoreCell_SampleLow], reasons == 0, names, reasons, sample[CoreCell_Capabilities], sample[CoreCell_Quality],
        sample[CoreCell_AttemptsHigh], sample[CoreCell_AttemptsLow], sample[CoreCell_DroppedHigh], sample[CoreCell_DroppedLow], sample[CoreCell_IgnoredHigh], sample[CoreCell_IgnoredLow], sample[CoreCell_PausedHigh], sample[CoreCell_PausedLow],
        view_as<float>(sample[CoreCell_Duration]), view_as<float>(sample[CoreCell_Interval]));
}

/** Append window identity only for the currently cached participant. */
void FormatNativeLogContext(int client, int userId, char[] text, int length)
{
    if (client > 0 && client <= MaxClients && g_CoreHasSample[client] && g_CoreSamples[client][CoreCell_UserId] == userId)
    {
        Format(text, length, "window_available=1 window_epoch=%d generation=%d window=%08x:%08x core_instance=%08x:%08x",
            g_CoreSamples[client][CoreCell_Epoch], g_CoreSamples[client][CoreCell_Generation], g_CoreSamples[client][CoreCell_SampleHigh], g_CoreSamples[client][CoreCell_SampleLow],
            g_CoreSamples[client][CoreCell_InstanceHigh], g_CoreSamples[client][CoreCell_InstanceLow]);
    }
    else strcopy(text, length, "window_available=0");
}

/** Called once per participant by the evaluation timer, never by status/API reads. */
bool EvaluateNativeWindow(int client, NativeCadenceWindow window)
{
    int sample[SPEEDWATCH_CORE_SAMPLE_CELLS];
    bool ready = bNativeDetectorReady();
    if (!ready || !ReadNativeObservation(client, sample))
    {
        g_CoreStates[client] = ready && sample[CoreCell_State] == view_as<int>(NativeObservation_Stale)
            ? NativeObservation_Stale : NativeObservation_Absent;
        LogNativeWindow(client, sample, false, ready ? WINDOW_UNAVAILABLE : WINDOW_CORE_NOT_READY);
        g_CoreWindowReady[client] = false;
        g_CoreHasSample[client] = false;
        return false;
    }
    int userId = GetClientUserId(client), serial = GetClientSerial(client), team = GetClientTeam(client);
    if (g_Log.bDebug(DEBUG_SAMPLES))
    {
        int reasons = NativeWindowRejectReasons(client, sample, userId, serial, team, g_Runtime.observationGeneration);
        LogNativeWindow(client, sample, true, reasons);
    }
    bool accepted = bAcceptNativeWindow(client, sample, userId, serial, team, g_Runtime.observationGeneration);
    if (!accepted)
    {
        return false;
    }
    window.commands = sample[CoreCell_AttemptsLow];
    window.duration = view_as<float>(sample[CoreCell_Duration]);
    window.interval = view_as<float>(sample[CoreCell_Interval]);
    return true;
}

void ShowNativeCoreStatus(int client)
{
    ReplyToCommand(client, "[SpeedWatch] detection_backend=native signal=run_command_attempts native_available=%d detector_ready=%d caps=%d pending=%d",
        g_Runtime.coreAvailable, bNativeDetectorReady(), g_Runtime.coreCapabilities, g_Runtime.coreNeedsSync);
    if (g_Runtime.coreAvailable)
    {
        ReplyToCommand(client, "[SpeedWatch] native_participants=%d native_reserved_bytes=%d native_max_bytes=%d executed_signal=0 physical_signal=0",
            SpeedWatchCore_GetStatus(0), SpeedWatchCore_GetStatus(1), SpeedWatchCore_GetStatus(2));
        for (int target = 1; target <= MaxClients; target++)
        {
            if (g_CoreHasSample[target] && g_bMonitor[target])
            {
                ReplyToCommand(client, "[SpeedWatch] native slot=%d sample=%d:%d quality=%d caps=%d attempts=%d:%d duration=%.3f evaluated=%d observation_state=%d",
                    target, g_CoreSamples[target][CoreCell_SampleHigh], g_CoreSamples[target][CoreCell_SampleLow], g_CoreSamples[target][CoreCell_Quality], g_CoreSamples[target][CoreCell_Capabilities],
                    g_CoreSamples[target][CoreCell_AttemptsHigh], g_CoreSamples[target][CoreCell_AttemptsLow], view_as<float>(g_CoreSamples[target][CoreCell_Duration]), g_bHasSample[target], g_CoreStates[target]);
            }
        }
    }
}

/** Rule-specific classification, independent of logging and engine reads. */
NativeObservationState eNativeObservationState(int reasons)
{
    if (reasons & WINDOW_CAPABILITIES) return NativeObservation_MissingCapability;
    if (reasons & WINDOW_INVALID_FIELDS) return NativeObservation_Invalid;
    if (reasons & WINDOW_DUPLICATE) return NativeObservation_Duplicate;
    if (reasons & (WINDOW_QUALITY | WINDOW_GAP | WINDOW_GENERATION | WINDOW_INSTANCE | WINDOW_IGNORED | WINDOW_PAUSED))
        return NativeObservation_Interrupted;
    if (reasons & WINDOW_FIRST) return NativeObservation_First;
    return NativeObservation_Published;
}
