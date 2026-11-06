#pragma once
#include "../../usioption.h"
#include <array>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <vector>

namespace YaneuraOu { namespace Eval {
namespace {
std::string psqt_path;
std::array<int16_t,637> psqt_weights{};
bool psqt_loaded=false;
bool tiny_loaded=false;
bool tiny_symmetric=false;
unsigned tiny_width=0,tiny_hidden=0;
std::vector<int16_t> tiny_embedding,tiny_fc,tiny_out;
std::vector<int32_t> tiny_bias,tiny_fc_bias;
int32_t tiny_out_bias=0;
unsigned tiny_generation=1;
bool tiny_verify=false;
uint64_t tiny_incremental_count=0,tiny_refresh_count=0,tiny_verification_count=0;

void psqt_stats() {
    std::printf("info string shogi1995 accumulators incremental=%llu refresh=%llu verified=%llu\n",
                (unsigned long long)tiny_incremental_count,(unsigned long long)tiny_refresh_count,
                (unsigned long long)tiny_verification_count);
    std::fflush(stdout);
}

template<class T> bool read_weights(FILE* file,std::vector<T>& values,size_t size) {
    values.resize(size);
    return std::fread(values.data(),sizeof(T),size,file)==size;
}

void psqt_options(OptionsMap& options) {
    options.add("EvalFile",Option("<none>",[](const Option& option) {
        psqt_path=std::string(option);psqt_loaded=false;tiny_loaded=false;
        if(++tiny_generation==0)++tiny_generation;
        return std::nullopt;
    }));
    options.add("EvalVerify",Option(false,[](const Option& option) {
        tiny_verify=bool(option);return std::nullopt;
    }));
}

void psqt_load() {
    if(psqt_loaded || psqt_path.empty() || psqt_path=="<none>")return;
    FILE* file=std::fopen(psqt_path.c_str(),"rb");
    char magic[8];uint32_t count=0;
    bool ok=file && std::fread(magic,1,8,file)==8;
    bool version1=ok && !std::memcmp(magic,"S95NN01\0",8);
    bool version2=ok && !std::memcmp(magic,"S95NN02\0",8);
    if(version1 || version2) {
        uint32_t header[4];
        ok=std::fread(header,4,4,file)==4 && (header[0]==171720 || (version2 && header[0]==95400)) && header[3]==2120
            && header[1]>=1 && header[1]<=32 && header[2]<=32 && (version2 || header[2]>=1);
        if(ok) {
            tiny_width=header[1];tiny_hidden=header[2];tiny_symmetric=header[0]==95400;
            ok=read_weights(file,tiny_embedding,size_t(header[0])*tiny_width)
                && read_weights(file,tiny_bias,tiny_width)
                && read_weights(file,tiny_fc,tiny_hidden*tiny_width*2)
                && read_weights(file,tiny_fc_bias,tiny_hidden)
                && read_weights(file,tiny_out,tiny_hidden?tiny_hidden:tiny_width*2)
                && std::fread(&tiny_out_bias,4,1,file)==1;
        }
        tiny_loaded=ok;
    } else if(ok) {
        ok=!std::memcmp(magic,"S95PSQ1\0",8) && std::fread(&count,4,1,file)==1 && count==637
            && std::fread(psqt_weights.data(),2,637,file)==637;
    }
    if(ok)ok=std::fgetc(file)==EOF;
    if(file)std::fclose(file);
    if(!ok) { std::printf("info string invalid evaluation file: %s\n",psqt_path.c_str());std::fflush(stdout);std::exit(1); }
    psqt_loaded=true;
    std::printf("info string shogi1995 %s loaded: %s\n",tiny_loaded?"tiny network":"PSQT",psqt_path.c_str());std::fflush(stdout);
}

void tiny_add(int* accumulator,int king,int feature,int count) {
    int king_index=tiny_symmetric?(king%9)*5+std::min(king/9,8-king/9):king;
    const int16_t* weights=tiny_embedding.data()+size_t(king_index*2120+feature)*tiny_width;
    for(unsigned j=0;j<tiny_width;++j)accumulator[j]+=int(weights[j])*count;
}

void tiny_board_change(int* accumulator,int king,int perspective,Piece piece,int square,int count) {
    if(piece==NO_PIECE || type_of(piece)==KING)return;
    int pt=int(type_of(piece));
    int index=pt<8?pt-1:pt-2;
    int relative=int(color_of(piece))!=perspective;
    int oriented=perspective?80-square:square;
    if(tiny_symmetric && king/9>4)oriented=(8-oriented/9)*9+oriented%9;
    tiny_add(accumulator,king,(relative*13+index)*81+oriented,count);
}

int tiny_hand_index(PieceType piece) {
    return piece<=SILVER?int(piece)-1:piece==GOLD?4:piece==BISHOP?5:6;
}

void tiny_full(const Position& pos,int perspective,int king,int* accumulator) {
    constexpr PieceType types[]={PAWN,LANCE,KNIGHT,SILVER,GOLD,BISHOP,ROOK};
    for(unsigned j=0;j<tiny_width;++j)accumulator[j]=tiny_bias[j];
    for(int square=0;square<81;++square)
        tiny_board_change(accumulator,king,perspective,pos.piece_on(Square(square)),square,1);
    for(int color=0;color<2;++color)
        for(int pt=0;pt<7;++pt) {
            int count=hand_count(pos.hand_of(Color(color)),types[pt]);
            if(count)tiny_add(accumulator,king,2106+(color!=perspective)*7+pt,count);
        }
}

int tiny_black(const Position& pos) {
    StateInfo* state=pos.state();
    if(state->tiny_generation!=tiny_generation) {
        for(int perspective=0;perspective<2;++perspective) {
            int king=int(pos.square<KING>(Color(perspective)));
            if(perspective)king=80-king;
            int* accumulator=state->tiny_accumulator[perspective];
            // Search can skip evaluation at check nodes. Recover from a nearby
            // computed ancestor before falling back to a complete board scan.
            const StateInfo* changes[8];unsigned count=0;
            const StateInfo* previous=state;
            while(previous && previous->tiny_generation!=tiny_generation && count<8) {
                bool king_moved=previous->tiny_before!=NO_PIECE && type_of(previous->tiny_before)==KING
                    && int(color_of(previous->tiny_before))==perspective;
                if(king_moved)break;
                changes[count++]=previous;
                previous=previous->previous;
            }
            if(previous && previous->tiny_generation==tiny_generation) {
                std::memcpy(accumulator,previous->tiny_accumulator[perspective],tiny_width*sizeof(int));
                while(count) {
                    const StateInfo* change=changes[--count];
                    if(change->tiny_to<0)continue;
                    tiny_board_change(accumulator,king,perspective,change->tiny_before,change->tiny_from,-1);
                    tiny_board_change(accumulator,king,perspective,change->tiny_after,change->tiny_to,1);
                    tiny_board_change(accumulator,king,perspective,change->tiny_captured,change->tiny_to,-1);
                    int relative=int(color_of(change->tiny_after))!=perspective;
                    if(change->tiny_from<0)
                        tiny_add(accumulator,king,2106+relative*7+tiny_hand_index(raw_type_of(change->tiny_after)),-1);
                    if(change->tiny_captured!=NO_PIECE)
                        tiny_add(accumulator,king,2106+relative*7+tiny_hand_index(raw_type_of(change->tiny_captured)),1);
                }
                ++tiny_incremental_count;
            } else {
                tiny_full(pos,perspective,king,accumulator);
                ++tiny_refresh_count;
            }
        }
        state->tiny_generation=tiny_generation;
    }
    if(tiny_verify) {
        for(int perspective=0;perspective<2;++perspective) {
            int king=int(pos.square<KING>(Color(perspective)));
            if(perspective)king=80-king;
            int full[32];tiny_full(pos,perspective,king,full);
            for(unsigned j=0;j<tiny_width;++j)
                if(full[j]!=state->tiny_accumulator[perspective][j]) {
                    std::printf("info string accumulator mismatch perspective=%d lane=%u cached=%d full=%d\n",
                                perspective,j,state->tiny_accumulator[perspective][j],full[j]);
                    std::fflush(stdout);std::exit(2);
                }
        }
        ++tiny_verification_count;
    }
    int32_t activation[64];
    int stm=int(pos.side_to_move());
    for(int relative=0;relative<2;++relative)
        for(unsigned j=0;j<tiny_width;++j)
            activation[relative*tiny_width+j]=std::max(0,std::min(128,state->tiny_accumulator[stm^relative][j]));
    int64_t output=tiny_out_bias;
    if(!tiny_hidden)
        for(unsigned j=0;j<tiny_width*2;++j)output+=activation[j]*int(tiny_out[j]);
    for(unsigned i=0;i<tiny_hidden;++i) {
        int32_t sum=tiny_fc_bias[i];
        for(unsigned j=0;j<tiny_width*2;++j)sum+=activation[j]*int(tiny_fc[i*tiny_width*2+j]);
        int value=sum<=0?0:std::min(128,int((sum+32)/64));
        output+=value*int(tiny_out[i]);
    }
    int correction=output>=0?int((output+128)/256):-int((-output+128)/256);
    int black=pos.state()->materialValue+(stm?-correction:correction);
    return std::max(-12000,std::min(12000,black));
}

int psqt_black(const Position& pos) {
    if(tiny_loaded)return tiny_black(pos);
    int score=0;
    for(int square=0;square<81;++square) {
        Piece piece=pos.piece_on(Square(square));
        if(piece==NO_PIECE)continue;
        bool white=color_of(piece)==WHITE;
        int oriented=white?80-square:square;
        int file=oriented/9,rank=oriented%9;
        int value=psqt_weights[(int(type_of(piece))-1)*45+rank*5+std::min(file,8-file)];
        score+=white?-value:value;
    }
    constexpr PieceType types[]={PAWN,LANCE,KNIGHT,SILVER,GOLD,BISHOP,ROOK};
    for(int i=0;i<7;++i)
        score+=(hand_count(pos.hand_of(BLACK),types[i])-hand_count(pos.hand_of(WHITE),types[i]))*psqt_weights[630+i];
    return std::max(-12000,std::min(12000,score));
}
}
}}
