#ifndef SHOGI1995_SINGLE_THREAD_COUNTER_H_INCLUDED
#define SHOGI1995_SINGLE_THREAD_COUNTER_H_INCLUDED

#include <atomic>
#include <cstdint>

namespace YaneuraOu {

// The SHOGI1995_SINGLE_THREAD worker and its readers execute synchronously.
// Keep the complete unsigned64 counter, including carry, without requiring
// atomic64 loads/stores (which use x87 integer conversions on this target).
// This class supplies no inter-thread synchronization.
class alignas(8) SingleThreadCounter64 {
   public:
    constexpr SingleThreadCounter64(std::uint64_t initial = 0) noexcept : value(initial) {}
    SingleThreadCounter64(const SingleThreadCounter64&) = delete;
    SingleThreadCounter64& operator=(const SingleThreadCounter64&) = delete;

    std::uint64_t load(std::memory_order = std::memory_order_seq_cst) const noexcept {
        return value;
    }

    void store(std::uint64_t desired,
               std::memory_order = std::memory_order_seq_cst) noexcept {
        value = desired;
    }

    std::uint64_t operator=(std::uint64_t desired) noexcept {
        store(desired);
        return desired;
    }

    operator std::uint64_t() const noexcept { return load(); }

   private:
    std::uint64_t value;
};

#if defined(SHOGI1995_SINGLE_THREAD)
using SearchNodeCounter = SingleThreadCounter64;
#else
using SearchNodeCounter = std::atomic<std::uint64_t>;
#endif

} // namespace YaneuraOu

#endif
