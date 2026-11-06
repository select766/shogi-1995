#pragma once
#include <functional>
#include <string>
namespace YaneuraOu {
void shogi1995_set_stop(std::function<void()> stop);
void shogi1995_poll();
bool shogi1995_getline(std::string& line);
void shogi1995_memory_stats();
void shogi1995_record_search(int completed_depth, unsigned long long nodes, long long milliseconds);
void shogi1995_search_stats();
}
