#include "SampleCodec.h"
#include <algorithm>
#include <cstring>
namespace speedwatch {
bool EncodeSample(const Snapshot* s, std::uint32_t version, std::int32_t* out, std::size_t length) {
    if (version != kApiVersion || !out || length < kSampleCells) return false;
    std::fill(out, out + kSampleCells, 0);
    out[CellApi] = kApiVersion; out[CellLength] = kSampleCells;
    if (!s) return false;
    auto cell = [&](int n, std::uint32_t v) { std::memcpy(out+n, &v, sizeof(v)); };
    auto wide = [&](int n, std::uint64_t v) { cell(n, static_cast<std::uint32_t>(v)); cell(n+1, static_cast<std::uint32_t>(v >> 32)); };
    out[CellSource] = 1; // source: native observation, never executed simulation
    cell(CellCapabilities,s->capabilities); cell(CellQuality,s->quality); out[CellUserId] = s->identity.userId;
    cell(CellSerial,s->identity.serial); cell(CellAccountId,s->identity.accountId); cell(CellEpoch,s->epoch); cell(CellGeneration,s->generation);
    wide(CellSampleLow,s->sampleId); wide(CellStartLow,s->startUs); wide(CellEndLow,s->endUs);
    out[CellStartTick]=s->startTick; out[CellEndTick]=s->endTick;
    std::memcpy(out+CellInterval,&s->interval,4);
    const float duration = s->endUs >= s->startUs ? static_cast<float>((s->endUs-s->startUs)/1.e6) : 0;
    std::memcpy(out+CellDuration,&duration,4);
    out[CellTeam]=s->team;
    wide(CellBlocksLow,s->counters.blocks); wide(CellNewCommandsLow,s->counters.newCommands); wide(CellTotalCommandsLow,s->counters.totalCommands);
    wide(CellDroppedLow,s->counters.droppedPackets); wide(CellIgnoredLow,s->counters.ignoredBlocks); wide(CellPausedLow,s->counters.pausedBlocks);
    wide(CellAttemptsLow,s->counters.runCommandAttempts); wide(CellDiscardedLow,s->counters.discarded); wide(CellInvocationLow,s->counters.lastInvocation);
    wide(CellLastBlockLow,s->counters.lastBlockUs); out[CellLastBlockTick]=s->counters.lastBlockTick;
    wide(CellLastRunLow,s->counters.lastRunUs); out[CellLastRunTick]=s->counters.lastRunTick;
    wide(CellInstanceLow,s->instanceId);
    out[CellState] = s->quality ? Interrupted : Published;
    return true;
}
}
