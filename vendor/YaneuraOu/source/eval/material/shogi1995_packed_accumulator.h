#pragma once
#include <cstdint>
#include <cstring>

namespace YaneuraOu { namespace Eval { namespace PackedAccumulator {

constexpr int bias=32768;
constexpr unsigned maximum_active_slots=40;

// Both biased lanes must stay in [0,65535], including every intermediate
// add/remove. Under that guard a signed low coefficient cannot borrow from,
// or carry into, the independently encoded high lane.
inline uint32_t encode(int low,int high) {
    return (uint32_t(low)+uint32_t(bias))|((uint32_t(high)+uint32_t(bias))<<16);
}
inline int low(uint32_t word) { return int(word&65535u)-bias; }
inline int high(uint32_t word) { return int(word>>16)-bias; }

inline uint32_t delta(int low_coefficient,int high_coefficient) {
    return uint32_t(low_coefficient)+(uint32_t(high_coefficient)<<16);
}
inline int signed16(uint32_t value) { return int(value&32767u)-int(value&32768u); }
inline int low_coefficient(uint32_t word) { return signed16(word); }
inline int high_coefficient(uint32_t word) {
    return signed16((word>>16)+unsigned(low_coefficient(word)<0));
}

// Fixed-size memcpy preserves the bit representation without aliasing an
// int16 embedding array through a uint32 pointer. The target is little-endian.
inline uint32_t read(const void* address) {
    uint32_t word;std::memcpy(&word,address,sizeof(word));return word;
}
inline void write(void* address,uint32_t word) { std::memcpy(address,&word,sizeof(word)); }
inline int lane(const int* accumulator,unsigned index) {
    uint32_t word=read(accumulator+index/2);
    return index&1?high(word):low(word);
}
inline int coefficient(const int16_t* weights,unsigned index) {
    uint32_t word=read(weights+(index&~1u));
    return index&1?high_coefficient(word):low_coefficient(word);
}

static_assert(sizeof(int)==4 && sizeof(int16_t)==2,"packed cache requires32-bit int and16-bit coefficients");
}}}
