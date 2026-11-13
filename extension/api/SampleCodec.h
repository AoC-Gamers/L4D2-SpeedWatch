#pragma once
#include "../telemetry/ObservationService.h"
namespace speedwatch {
constexpr std::size_t kSampleCells = 48;
// Does not touch the destination on bad version/length. Larger buffers keep their tail.
bool EncodeSample(const Snapshot* sample, std::uint32_t version, std::int32_t* out, std::size_t length);
}
