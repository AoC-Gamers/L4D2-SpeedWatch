#pragma once
#include <array>
#include <cstdint>
#include <memory>
#include <cstddef>

namespace speedwatch {
constexpr int kMaxSlots = 256; // Explicit limit; extension rejects larger servers.
constexpr std::uint32_t kApiVersion = 1;
enum Capability : std::uint32_t { Blocks = 1, RunAttempts = 2, TeamContext = 4 };
enum Quality : std::uint32_t { InvalidMetadata = 1, Overflow = 2, ClockDiscontinuity = 4,
    TickDiscontinuity = 8, UnavailableHook = 16, ParticipantChanged = 32 };
struct Identity { int userId = 0; std::uint32_t serial = 0, accountId = 0; };
struct Counters {
    std::uint64_t blocks = 0, newCommands = 0, totalCommands = 0, droppedPackets = 0;
    std::uint64_t ignoredBlocks = 0, pausedBlocks = 0, runCommandAttempts = 0, discarded = 0;
    std::uint64_t lastInvocation = 0, lastBlockUs = 0, lastRunUs = 0;
    int lastBlockTick = 0, lastRunTick = 0;
};
struct Snapshot {
    Identity identity;
    std::uint64_t sampleId = 0, startUs = 0, endUs = 0;
    std::uint32_t epoch = 0, generation = 0, capabilities = 0, quality = 0;
    int startTick = 0, endTick = 0, team = 0;
    float interval = 0;
    Counters counters;
};
struct Participant {
    int slot = 0;
    Identity identity;
    std::uint32_t generation = 0, capabilities = 0, quality = 0;
    int team = 0;
    Counters counters;
    Snapshot sample;
    bool hasSample = false;
};
class ObservationService {
public:
    bool SetParticipant(int slot, Identity identity, int team, bool eligible, std::uint32_t capabilities);
    void Remove(int slot);
    void Reset();
    // Sole window authority. Queries never close or consume a window.
    bool Pulse(bool enabled, std::uint32_t epoch, std::uint64_t nowUs, int tick, float interval);
    void Block(int slot, std::uint64_t nowUs, int numcmds, int totalcmds, int dropped, bool ignore, bool paused, int tick = 0);
    void RunAttempt(int slot, std::uint64_t nowUs, int tick = 0);
    const Snapshot* Sample(int slot, std::uint64_t nowUs) const;
    bool Active(int slot, std::uint64_t nowUs) const;
    std::size_t Count() const { return count_; }
    std::size_t MemoryUsed() const { return count_ * sizeof(Participant) + sizeof(*this); }
    std::uint64_t LastSampleId() const { return sampleId_; }
private:
    Participant* Find(int slot) const;
    std::array<std::unique_ptr<Participant>, kMaxSlots + 1> records_{};
    std::uint32_t generation_ = 0, epoch_ = 0;
    std::uint64_t sampleId_ = 0, invocation_ = 0, startUs_ = 0;
    int startTick_ = 0;
    float interval_ = 0;
    bool enabled_ = false;
    std::size_t count_ = 0;
};
void SaturatingAdd(std::uint64_t& target, std::uint64_t amount, std::uint32_t& quality);
} // namespace speedwatch
