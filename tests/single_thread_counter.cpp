#include "single_thread_counter.h"

#include <array>
#include <atomic>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <limits>
#include <type_traits>

using YaneuraOu::SingleThreadCounter64;

#if defined(SHOGI1995_SINGLE_THREAD)
static_assert(std::is_same<YaneuraOu::SearchNodeCounter, SingleThreadCounter64>::value,
              "single-thread build must select the full-width plain counter");
#else
static_assert(std::is_same<YaneuraOu::SearchNodeCounter, std::atomic<std::uint64_t>>::value,
              "ordinary threaded builds must retain atomic counters");
#endif
static_assert(!std::is_copy_constructible<SingleThreadCounter64>::value,
              "match the atomic counter's non-copyable ownership");
static_assert(!std::is_copy_assignable<SingleThreadCounter64>::value,
              "match the atomic counter's non-copyable ownership");
static_assert(sizeof(SingleThreadCounter64) == sizeof(std::uint64_t), "retain64 bits");

int main() {
    constexpr std::uint64_t top = std::numeric_limits<std::uint64_t>::max();
    const std::array<std::uint64_t, 12> seeds{{
        0, 1, 15, 16, 0x7fffffffULL, 0xfffffffeULL, 0xffffffffULL,
        0x100000000ULL, 0x100000001ULL, 0x7fffffffffffffffULL, top - 1, top}};
    SingleThreadCounter64 counter(0), independent(17);
    std::atomic<std::uint64_t> reference(0);
    std::uint64_t cases = 0;
    for (auto seed : seeds) {
        assert((counter = seed) == (reference = seed));
        assert(std::uint64_t(counter) == std::uint64_t(reference));
        assert(counter.load() == seed);
        for (unsigned step = 0; step < 33; ++step) {
            // The engine's public counter protocol, including both32/64-bit carries.
            counter.store(counter.load(std::memory_order_relaxed) + 1, std::memory_order_relaxed);
            reference.store(reference.load(std::memory_order_relaxed) + 1, std::memory_order_relaxed);
            assert(counter.load(std::memory_order_relaxed) == reference.load(std::memory_order_relaxed));
            assert((counter.load(std::memory_order_relaxed) & 15) ==
                   (reference.load(std::memory_order_relaxed) & 15));
            assert(independent.load() == 17);
            ++cases;
        }
    }
    std::uint64_t random = 0x9e3779b97f4a7c15ULL;
    for (unsigned i = 0; i < 10000; ++i) {
        random ^= random << 13;
        random ^= random >> 7;
        random ^= random << 17;
        counter.store(random);
        reference.store(random);
        assert(std::uint64_t(counter) == std::uint64_t(reference));
        counter.store(counter.load(std::memory_order_relaxed) + 1, std::memory_order_relaxed);
        reference.store(reference.load(std::memory_order_relaxed) + 1, std::memory_order_relaxed);
        assert(counter.load() == reference.load());
        ++cases;
    }
    counter.store(0xffffffffULL);
    counter.store(counter.load() + 1);
    assert(counter.load() == 0x100000000ULL);
    counter.store(top);
    counter.store(counter.load() + 1);
    assert(counter.load() == 0);
    std::cout << "{\"passed\":true,\"cases\":" << cases
              << ",\"unsigned32_carry\":true,\"unsigned64_wrap\":true}\n";
}
