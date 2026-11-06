#include "shogi1995.h"
#include <cerrno>
#include <deque>
#include <sys/select.h>
#include <unistd.h>
#include <cstdio>
namespace YaneuraOu {
void shogi1995_memory_stats() {
    // Frozen Linux 1.2 i386 sysinfo layout, measured inside the guest.
    unsigned values[16]={};
    if(syscall(116,values)==0) {
        std::printf("info string shogi1995 memory total=%u free=%u swap=%u\n",values[4],values[5],values[8]);
        std::fflush(stdout);
    }
}
namespace {
std::string input;
std::deque<std::string> pending;
std::function<void()> stop_search;
bool ended=false;
void receive() {
    char buf[1024];
    auto n=read(0,buf,sizeof buf);
    if(n==0 || (n<0 && errno!=EINTR)) ended=true;
    if(n>0) input.append(buf,n);
}
bool extract(std::string& line) {
    auto i=input.find('\n');
    if(i==std::string::npos) return false;
    line=input.substr(0,i);
    input.erase(0,i+1);
    if(!line.empty() && line.back()=='\r') line.pop_back();
    return true;
}
}
void shogi1995_set_stop(std::function<void()> stop) { stop_search=std::move(stop); }
void shogi1995_poll() {
    fd_set ready;
    FD_ZERO(&ready); FD_SET(0,&ready);
    timeval tv={0,0};
    if(!ended && select(1,&ready,nullptr,nullptr,&tv)>0) receive();
    std::string line;
    while(extract(line)) {
        auto token=line.substr(0,line.find_first_of(" \t"));
        if(token=="stop" || token=="quit" || token=="gameover") {
            if(stop_search) stop_search();
            if(token!="stop") pending.push_back(line);
        } else pending.push_back(line);
    }
    if(ended && stop_search) stop_search();
}
bool shogi1995_getline(std::string& line) {
    if(!pending.empty()) { line=std::move(pending.front()); pending.pop_front(); return true; }
    while(!extract(line)) {
        if(ended) return false;
        receive();
    }
    return true;
}
}
