#include <chrono>
#include <cstdint>
std::uint64_t SpeedWatchNowUs() {
    return static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::microseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count());
}
