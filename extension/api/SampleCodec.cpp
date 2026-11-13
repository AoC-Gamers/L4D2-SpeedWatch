#include "SampleCodec.h"
#include <algorithm>
#include <cstring>
namespace speedwatch {
bool EncodeSample(const Snapshot* s, std::uint32_t version, std::int32_t* out, std::size_t length) {
    if (version != kApiVersion || !out || length < kSampleCells) return false;
    std::fill(out, out + kSampleCells, 0);
    out[0] = kApiVersion; out[1] = kSampleCells;
    if (!s) return false;
    auto cell = [&](int n, std::uint32_t v) { std::memcpy(out+n, &v, sizeof(v)); };
    auto wide = [&](int n, std::uint64_t v) { cell(n, static_cast<std::uint32_t>(v)); cell(n+1, static_cast<std::uint32_t>(v >> 32)); };
    out[2] = 1; // source: native observation, never executed simulation
    cell(3,s->capabilities); cell(4,s->quality); out[5] = s->identity.userId;
    cell(6,s->identity.serial); cell(7,s->identity.accountId); cell(8,s->epoch); cell(9,s->generation);
    wide(10,s->sampleId); wide(12,s->startUs); wide(14,s->endUs);
    out[16]=s->startTick; out[17]=s->endTick;
    std::memcpy(out+18,&s->interval,4);
    const float duration = s->endUs >= s->startUs ? static_cast<float>((s->endUs-s->startUs)/1.e6) : 0;
    std::memcpy(out+19,&duration,4);
    out[20]=s->team;
    wide(21,s->counters.blocks); wide(23,s->counters.newCommands); wide(25,s->counters.totalCommands);
    wide(27,s->counters.droppedPackets); wide(29,s->counters.ignoredBlocks); wide(31,s->counters.pausedBlocks);
    wide(33,s->counters.runCommandAttempts); wide(35,s->counters.discarded); wide(37,s->counters.lastInvocation);
    wide(39,s->counters.lastBlockUs); out[41]=s->counters.lastBlockTick;
    wide(42,s->counters.lastRunUs); out[44]=s->counters.lastRunTick;
    // 45..47 reserved, always zero. Unsupported groups have no capability bit.
    return true;
}
}
