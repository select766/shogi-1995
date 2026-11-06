#include <cstdio>
#include <cstdlib>
#include <vector>
#include <string>
#include <chrono>
int main() {
    std::puts("C++ runtime entered");
    std::fflush(stdout);
    std::vector<std::string> values(1000, "Pentium Linux 1.2.13");
    auto time = std::chrono::steady_clock::now().time_since_epoch().count();
    std::printf("runtime OK: %s, entries=%u, clock=%lld\n",
                values[0].c_str(), unsigned(values.size()), (long long)time);
}
