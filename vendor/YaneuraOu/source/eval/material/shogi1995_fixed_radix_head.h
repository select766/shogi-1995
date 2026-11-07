#pragma once
#include <array>
#include <cstdint>

namespace YaneuraOu { namespace Eval { namespace FixedRadixHead {

// Arithmetic specialization of the already frozen128m width8/H0 head.
// The engine must check the loaded coefficients/bias before selecting this path.
// This does not change the model file, activations, output scale, or rounding.
constexpr std::array<int16_t, 16> weights{{
    -1113, -1130, -1058, -1013, 1211, 1334, -1222, -1115,
     1384,  1520,  1319,  1272, -922, -1401, 1553, 1376}};
constexpr int32_t bias = -36795;

constexpr int center(int value) {
    const int shifted = value + 128;
    return (shifted >= 0 ? shifted / 256 : -((-shifted + 255) / 256)) * 256;
}

constexpr uint32_t coefficients(unsigned even) {
    return uint32_t(weights[even + 1] - center(weights[even + 1]) + 128)
         | (uint32_t(weights[even] - center(weights[even]) + 128) << 16);
}

inline bool matches(const int16_t* loaded, int32_t loaded_bias,
                    unsigned width, unsigned hidden) {
    if (width != 8 || hidden != 0 || loaded_bias != bias)
        return false;
    for (unsigned i = 0; i < weights.size(); ++i)
        if (loaded[i] != weights[i])
            return false;
    return true;
}

inline int32_t pair(int32_t even, int32_t odd, uint32_t packed_coefficients) {
    // Preconditions: activations in[0,128], residual coefficients in[-128,127].
    // Low product<=32640, middle coefficient<=65280: no16-bit lane carry.
    // The discarded upper32 bits and uint32 overflow are intentional.
    const uint32_t lanes = uint32_t(even) | (uint32_t(odd) << 16);
    const uint32_t product = lanes * packed_coefficients;
    return int32_t(product >> 16);
}

inline int32_t raw(const int32_t* a) {
    int32_t sum = bias;
    sum += pair(a[0], a[1], coefficients(0));
    sum += pair(a[2], a[3], coefficients(2));
    sum += pair(a[4], a[5], coefficients(4));
    sum += pair(a[6], a[7], coefficients(6));
    sum += pair(a[8], a[9], coefficients(8));
    sum += pair(a[10], a[11], coefficients(10));
    sum += pair(a[12], a[13], coefficients(12));
    sum += pair(a[14], a[15], coefficients(14));
    const int32_t d0 = (a[4] + a[5] + a[8] + a[10] + a[11] + a[15])
                     - (a[0] + a[1] + a[2] + a[3] + a[7] + a[12]);
    const int32_t d1 = (a[9] + a[14]) - (a[6] + a[13]);
    // |d0|<=768, |d1|<=256. Expanded raw output is within[-1281979,1730629].
    // Use multiplication: left-shifting a negative signed value would be UB.
    return sum + (9 * d0 + 11 * d1) * 128;
}

}}}
