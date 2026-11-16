/** Versioned native observation windows; the cadence detector consumes RunAttempts. */
#if defined _l4d2_speedwatch_core_included
    #endinput
#endif
#define _l4d2_speedwatch_core_included
#define SPEEDWATCH_CORE_API_VERSION 2
#define SPEEDWATCH_CORE_SAMPLE_CELLS 48
#define SPEEDWATCH_CORE_CAP_BLOCKS 1
#define SPEEDWATCH_CORE_CAP_RUN_ATTEMPTS 2
#define SPEEDWATCH_CORE_CAP_TEAM 4
// Each rule names the groups it needs. Shared clock/identity faults affect all groups.
#define SPEEDWATCH_QUALITY_TIMING (4 | 8 | 32)
#define SPEEDWATCH_QUALITY_BLOCKS (1 | 2 | 16 | SPEEDWATCH_QUALITY_TIMING)
#define SPEEDWATCH_QUALITY_ATTEMPTS (2 | 16 | SPEEDWATCH_QUALITY_TIMING)
#define SPEEDWATCH_QUALITY_KNOWN (SPEEDWATCH_QUALITY_BLOCKS | SPEEDWATCH_QUALITY_ATTEMPTS)
#define CoreCell_Api 0
#define CoreCell_Length 1
#define CoreCell_Source 2
#define CoreCell_Capabilities 3
#define CoreCell_Quality 4
#define CoreCell_UserId 5
#define CoreCell_Serial 6
#define CoreCell_AccountId 7
#define CoreCell_Epoch 8
#define CoreCell_Generation 9
#define CoreCell_SampleLow 10
#define CoreCell_SampleHigh 11
#define CoreCell_StartLow 12
#define CoreCell_StartHigh 13
#define CoreCell_EndLow 14
#define CoreCell_EndHigh 15
#define CoreCell_StartTick 16
#define CoreCell_EndTick 17
#define CoreCell_Interval 18
#define CoreCell_Duration 19
#define CoreCell_Team 20
#define CoreCell_BlocksLow 21
#define CoreCell_BlocksHigh 22
#define CoreCell_NewCommandsLow 23
#define CoreCell_NewCommandsHigh 24
#define CoreCell_TotalCommandsLow 25
#define CoreCell_TotalCommandsHigh 26
#define CoreCell_DroppedLow 27
#define CoreCell_DroppedHigh 28
#define CoreCell_IgnoredLow 29
#define CoreCell_IgnoredHigh 30
#define CoreCell_PausedLow 31
#define CoreCell_PausedHigh 32
#define CoreCell_AttemptsLow 33
#define CoreCell_AttemptsHigh 34
#define CoreCell_DiscardedLow 35
#define CoreCell_DiscardedHigh 36
#define CoreCell_InvocationLow 37
#define CoreCell_InvocationHigh 38
#define CoreCell_LastBlockLow 39
#define CoreCell_LastBlockHigh 40
#define CoreCell_LastBlockTick 41
#define CoreCell_LastRunLow 42
#define CoreCell_LastRunHigh 43
#define CoreCell_LastRunTick 44
#define CoreCell_InstanceLow 45
#define CoreCell_InstanceHigh 46
#define CoreCell_State 47
enum NativeObservationState
{
    NativeObservation_Absent = 0,
    NativeObservation_Published,
    NativeObservation_Stale,
    NativeObservation_Interrupted,
    NativeObservation_MissingCapability,
    NativeObservation_Invalid,
    NativeObservation_First,
    NativeObservation_Duplicate
};
#define SPEEDWATCH_WINDOW_MIN_SECONDS 0.5
#define SPEEDWATCH_WINDOW_MAX_SECONDS 2.0
/**
 * Cells: 0 API, 1 length, 2 source (1 native), 3 availability mask, 4 quality,
 * 5 userid, 6 serial, 7 AccountID, 8 epoch, 9 participant generation.
 * 10/11 sample_id, 12/13 start_us, 14/15 end_us: uint64 low/high bit patterns.
 * 16/17 server ticks; 18 interval and 19 duration: float bit patterns; 20 team.
 * Uint64 pairs: 21 blocks, 23 numcmds sum, 25 totalcmds sum, 27 dropped_packets sum,
 * 29 ignore blocks, 31 paused blocks, 33 runCommandAttempts, 35 discarded metadata,
 * 37 last invocation ID. 39 last block us, 41 last block tick, 42 last run us,
 * 44 last run tick; 45/46 core instance: uint64 low/high; 47 state (absent/published/stale/interrupted).
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
 * False if absent or older than 2 seconds. Header 0/1 and state 47 survive; remaining cells zero.
 * Version/short buffer/invalid client throw a native error without writing output.
 * Writes exactly 48 cells; oversized buffers retain their tail. Caller supplies actual capacity.
 */
native bool SpeedWatchCore_GetSample(int client, int[] sample, int length, int version = SPEEDWATCH_CORE_API_VERSION);
/** 0 active records; 1 reserved bytes; 2 maximum bytes.
 * 3 controller relative to caller: 0 unowned, 1 caller, 2 another plugin. Read-only. */
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
