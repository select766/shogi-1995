#include "eval/material/shogi1995_fixed_radix_head.h"

#include <array>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iostream>

namespace Head = YaneuraOu::Eval::FixedRadixHead;

int main(int argc, char** argv) {
    assert(argc == 2);
    // Independent reference coefficients come from the actual frozen model,
    // not from the specialization's duplicated coefficient table.
    std::ifstream file(argv[1], std::ios::binary);
    assert(file);
    char magic[8];
    std::array<uint32_t, 4> header;
    file.read(magic, sizeof magic);
    file.read(reinterpret_cast<char*>(header.data()), sizeof header);
    assert(file && !std::memcmp(magic, "S95NN03\0", 8));
    assert(header[0] == 125388 && header[1] == 8 && header[2] == 0 && header[3] == 1548);
    file.seekg(24 + uint64_t(header[0]) * header[1] * 2 + header[1] * 4);
    std::array<int16_t, 16> weights;
    int32_t bias;
    file.read(reinterpret_cast<char*>(weights.data()), sizeof weights);
    file.read(reinterpret_cast<char*>(&bias), sizeof bias);
    assert(file && file.peek() == std::char_traits<char>::eof());
    assert(Head::matches(weights.data(), bias, 8, 0));
    assert(!Head::matches(weights.data(), bias + 1, 8, 0));
    assert(!Head::matches(weights.data(), bias, 16, 0));
    assert(!Head::matches(weights.data(), bias, 8, 8));
    assert(!Head::matches(nullptr, bias, 0, 0));
    for (unsigned lane = 0; lane < weights.size(); ++lane) {
        auto changed = weights;
        ++changed[lane];
        assert(!Head::matches(changed.data(), bias, 8, 0));
    }
    std::array<int32_t, 16> activation{};
    uint64_t cases = 0;
    auto check = [&]() {
        int64_t expected = bias;
        for (unsigned i = 0; i < weights.size(); ++i)
            expected += int64_t(activation[i]) * weights[i];
        const int32_t actual = Head::raw(activation.data());
        assert(actual == expected);
        ++cases;
    };
    for (int32_t value : {0, 1, 127, 128}) {
        activation.fill(value);
        check();
    }
    for (unsigned lane = 0; lane < weights.size(); ++lane) {
        activation.fill(0);
        for (int32_t value = 0; value <= 128; ++value) {
            activation[lane] = value;
            check();
        }
    }
    for (unsigned pair = 0; pair < 8; ++pair) {
        activation.fill(0);
        for (int32_t a = 0; a <= 128; ++a)
            for (int32_t b = 0; b <= 128; ++b) {
                activation[pair * 2] = a;
                activation[pair * 2 + 1] = b;
                check();
            }
    }
    uint64_t random = 0x9e3779b97f4a7c15ULL;
    for (unsigned repeat = 0; repeat < 10000; ++repeat) {
        for (auto& a : activation) {
            random ^= random << 13;
            random ^= random >> 7;
            random ^= random << 17;
            a = int32_t(random % 129);
        }
        check();
    }
    std::cout << "{\"passed\":true,\"cases\":" << cases
              << ",\"model_head_guard\":true,\"pair_domains_exhaustive\":true}\n";
}
