#include "ObservationService.h"
#include <cmath>
#include <limits>
namespace speedwatch {
void SaturatingAdd(std::uint64_t& target, std::uint64_t amount, std::uint32_t& quality) {
    if (amount > std::numeric_limits<std::uint64_t>::max() - target) {
        target = std::numeric_limits<std::uint64_t>::max(); quality |= Overflow;
    } else { target += amount; }
}
Participant* ObservationService::Find(int slot) const {
    return slot > 0 && slot <= kMaxSlots ? records_[slot].get() : nullptr;
}
bool ObservationService::SetParticipant(int slot, Identity id, int team, bool eligible, std::uint32_t caps) {
    if (slot < 1 || slot > kMaxSlots) return false;
    if (!eligible || id.userId <= 0 || id.serial == 0 || (team != 2 && team != 3)) { Remove(slot); return true; }
    Participant* p = Find(slot);
    if (p && (p->identity.serial != id.serial || p->identity.userId != id.userId || p->team != team || p->capabilities != caps)) {
        Remove(slot); p = nullptr;
    }
    if (!p) {
        records_[slot].reset(new Participant()); p = Find(slot); ++count_;
        p->slot = slot; p->generation = ++generation_; p->capabilities = caps; p->team = team;
        p->quality = ParticipantChanged;
    }
    p->identity = id; // Authorization may arrive later, without inventing an earlier identity.
    return true;
}
void ObservationService::Remove(int slot) {
    if (Find(slot)) { records_[slot].reset(); --count_; }
}
void ObservationService::Reset() {
    enabled_ = false; ++epoch_;
    for (auto& p : records_) if (p) { p->counters = {}; p->hasSample = false; p->quality = 0; }
}
bool ObservationService::Active(int slot, std::uint64_t now) const {
    return enabled_ && Find(slot) && now >= startUs_ && now - startUs_ <= 2500000;
}
bool ObservationService::Pulse(bool enabled, std::uint32_t epoch, std::uint64_t now, int tick, float interval) {
    if (!std::isfinite(interval) || interval <= 0 || !enabled) { Reset(); epoch_ = epoch; return false; }
    const bool continuing = enabled_ && epoch == epoch_;
    const bool clocks = now >= startUs_ && now - startUs_ >= 500000 && now - startUs_ <= 2000000;
    const std::int64_t ticks = static_cast<std::int64_t>(tick) - startTick_;
    const double expected = now >= startUs_ ? (now - startUs_) / 1.e6 / interval : 0;
    const bool stable = std::fabs(interval - interval_) < 0.000001f;
    const bool ticksValid = ticks >= expected * .8 && ticks <= expected * 1.2;
    const bool publish = continuing && clocks && stable && ticksValid;
    if (continuing) ++sampleId_;
    for (auto& p : records_) if (p) {
        if (continuing) {
            Snapshot s;
            s.identity = p->identity; s.sampleId = sampleId_; s.epoch = epoch_; s.generation = p->generation;
            s.startUs = startUs_; s.endUs = now; s.startTick = startTick_; s.endTick = tick; s.interval = interval_;
            s.capabilities = p->capabilities; s.quality = p->quality; s.team = p->team; s.counters = p->counters;
            if (!clocks || !stable) s.quality |= ClockDiscontinuity;
            if (!ticksValid) s.quality |= TickDiscontinuity;
            p->sample = s; p->hasSample = true;
        } else { p->hasSample = false; }
        p->counters = {}; p->quality = 0;
    }
    epoch_ = epoch; enabled_ = true; startUs_ = now; startTick_ = tick; interval_ = interval;
    return publish;
}
void ObservationService::Block(int slot, std::uint64_t now, int num, int total, int dropped, bool ignore, bool paused, int tick) {
    if (!Active(slot, now)) return;
    auto& p = *Find(slot);
    if (num < 0 || total < num || total > 65535 || dropped < 0 || dropped > 65535) {
        p.quality |= InvalidMetadata; SaturatingAdd(p.counters.discarded, 1, p.quality); return;
    }
    p.counters.lastBlockUs = now; p.counters.lastBlockTick = tick;
    SaturatingAdd(p.counters.blocks, 1, p.quality);
    SaturatingAdd(p.counters.newCommands, static_cast<std::uint64_t>(num), p.quality);
    SaturatingAdd(p.counters.totalCommands, static_cast<std::uint64_t>(total), p.quality);
    SaturatingAdd(p.counters.droppedPackets, static_cast<std::uint64_t>(dropped), p.quality);
    if (ignore) SaturatingAdd(p.counters.ignoredBlocks, 1, p.quality);
    if (paused) SaturatingAdd(p.counters.pausedBlocks, 1, p.quality);
}
void ObservationService::RunAttempt(int slot, std::uint64_t now, int tick) {
    if (!Active(slot, now)) return;
    auto& p = *Find(slot);
    if (!(p.capabilities & RunAttempts)) return;
    p.counters.lastRunUs = now; p.counters.lastRunTick = tick;
    SaturatingAdd(p.counters.runCommandAttempts, 1, p.quality);
    SaturatingAdd(invocation_, 1, p.quality); p.counters.lastInvocation = invocation_;
}
const Snapshot* ObservationService::Sample(int slot, std::uint64_t now) const {
    const auto* p = Find(slot);
    if (!enabled_ || !p || !p->hasSample || now < p->sample.endUs || now - p->sample.endUs > 2000000) return nullptr;
    return &p->sample;
}
} // namespace speedwatch
