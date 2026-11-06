#pragma once
#include <cstdint>

namespace YaneuraOu { namespace Eval { namespace PackedFC {

struct Activation {
    uint32_t lanes;
    int32_t correction;
};

// Preconditions: activations in [0,128], coefficients in [-128,127].
// The low product is at most32640 and the middle coefficient at most65280,
// so neither carries across a16-bit lane. Unsigned overflow is intentional.
inline Activation activation(int32_t a,int32_t b) {
    return {uint32_t(a)|(uint32_t(b)<<16),(a+b)*128};
}

inline uint32_t coefficients(int32_t u,int32_t v) {
    return uint32_t(v+128)|(uint32_t(u+128)<<16);
}

inline int32_t dot(Activation a,uint32_t weights) {
    uint32_t product=a.lanes*weights;
    return int32_t(product>>16)-a.correction;
}

}}}
