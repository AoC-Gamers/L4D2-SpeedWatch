/** Independent experimental diagnostics; never changes SpeedWatchSample or alert semantics. */
#if defined _l4d2_speedwatch_core_included
    #endinput
#endif
#define _l4d2_speedwatch_core_included
#define SPEEDWATCH_CORE_API_VERSION 1
#define SPEEDWATCH_CORE_SAMPLE_CELLS 48
#define SPEEDWATCH_CORE_CAP_BLOCKS 1
#define SPEEDWATCH_CORE_CAP_RUN_ATTEMPTS 2
#define SPEEDWATCH_CORE_CAP_TEAM 4
/**
 * Cells: 0 API, 1 length, 2 source (1 native), 3 availability mask, 4 quality,
 * 5 userid, 6 serial, 7 AccountID, 8 epoch, 9 participant generation.
 * 10/11 sample_id, 12/13 start_us, 14/15 end_us: uint64 low/high bit patterns.
 * 16/17 server ticks; 18 interval and 19 duration: float bit patterns; 20 team.
 * Uint64 pairs: 21 blocks, 23 numcmds sum, 25 totalcmds sum, 27 dropped_packets sum,
 * 29 ignore blocks, 31 paused blocks, 33 runCommandAttempts, 35 discarded metadata,
 * 37 last invocation ID. 39 last block us, 41 last block tick, 42 last run us,
 * 44 last run tick; 45..47 reserved zero.
 * Steady-clock microseconds are not Unix time or GetEngineTime(). No executed counter.
 * Availability is independent per group. Quality != 0 means degraded evidence.
 */
native int SpeedWatchCore_GetApiVersion();
native int SpeedWatchCore_GetCapabilities();
/** Single controller only. Closes one window per timer evaluation; false invalidates history.
 * Epoch changes restart observation; no window is published across a change.
 * Only the owning SpeedWatch plugin calls Pulse/SetParticipant. Read APIs are shared.
 */
native bool SpeedWatchCore_Pulse(bool enabled, int epoch);
native bool SpeedWatchCore_SetParticipant(int client, bool enabled);
/** Latest immutable window; repeat reads do not consume it. No backlog; sample IDs expose gaps.
 * False if absent or older than 2 seconds. Header 0/1 survives, remaining cells zero.
 * Version/short buffer/invalid client throw a native error without writing output.
 * Writes exactly 48 cells; oversized buffers retain their tail. Caller supplies actual capacity.
 */
native bool SpeedWatchCore_GetSample(int client, int[] sample, int length, int version = SPEEDWATCH_CORE_API_VERSION);
/** 0 active records; 1 bytes currently reserved by service and records; 2 maximum bytes. */
native int SpeedWatchCore_GetStatus(int field);
public Extension __ext_l4d2_speedwatch_core =
{
    name = "L4D2 SpeedWatch Core",
    file = "l4d2_speedwatch_core.ext",
    autoload = 1,
#if defined REQUIRE_EXTENSIONS
    required = 1,
#else
    required = 0,
#endif
};
#if !defined REQUIRE_EXTENSIONS
public void __ext_l4d2_speedwatch_core_SetNTVOptional()
{
    MarkNativeAsOptional("SpeedWatchCore_GetApiVersion");
    MarkNativeAsOptional("SpeedWatchCore_GetCapabilities");
    MarkNativeAsOptional("SpeedWatchCore_Pulse");
    MarkNativeAsOptional("SpeedWatchCore_SetParticipant");
    MarkNativeAsOptional("SpeedWatchCore_GetSample");
    MarkNativeAsOptional("SpeedWatchCore_GetStatus");
}
#endif
