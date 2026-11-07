#pragma once
#include "../../usioption.h"
#include <array>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <limits>
#include <vector>
#include "shogi1995_packed_fc.h"
#include "shogi1995_packed_accumulator.h"
#include "shogi1995_fixed_radix_head.h"

namespace YaneuraOu { namespace Eval {
namespace {
std::string psqt_path;
std::array<int16_t,637> psqt_weights{};
bool psqt_loaded=false;
bool tiny_loaded=false;
bool halfkp_linear_loaded=false;
std::vector<int32_t> halfkp_linear_weights;
bool tiny_symmetric=false;
bool tiny_standard_halfkp=false;
unsigned tiny_width=0,tiny_hidden=0;
std::vector<int16_t> tiny_embedding,tiny_fc,tiny_out;
std::vector<int32_t> tiny_bias,tiny_fc_bias;
int32_t tiny_out_bias=0;
bool tiny_output32=false;
bool tiny_fc_packed32=false;
bool tiny_accumulator_packed=false;
bool tiny_fixed_radix=false;
std::vector<uint32_t> tiny_fc_pairs;
unsigned tiny_generation=1;
bool tiny_verify=false;
uint64_t tiny_incremental_count=0,tiny_refresh_count=0,tiny_verification_count=0;
uint64_t tiny_radix_verification_count=0;

void psqt_stats() {
    unsigned kernel_width=tiny_loaded && tiny_standard_halfkp && (tiny_width==8 || tiny_width==16)?tiny_width:0;
    std::printf("info string shogi1995 accumulators incremental=%llu refresh=%llu verified=%llu output_bits=%u kernel_width=%u fc_packed=%u fc_bits=%u accumulator_packed=%u accumulator_bits=%u head_radix=%u head_verified=%llu\n",
                (unsigned long long)tiny_incremental_count,(unsigned long long)tiny_refresh_count,
                (unsigned long long)tiny_verification_count,unsigned(tiny_loaded?(tiny_output32?32:64):0),kernel_width,
                unsigned(tiny_loaded && tiny_fc_packed32),unsigned(tiny_loaded && tiny_hidden?(tiny_fc_packed32?32:64):0),
                unsigned(tiny_loaded && tiny_accumulator_packed),unsigned(tiny_loaded?(tiny_accumulator_packed?16:32):0),
                unsigned(tiny_loaded && tiny_fixed_radix),(unsigned long long)tiny_radix_verification_count);
    std::fflush(stdout);
}

template<class T> bool read_weights(FILE* file,std::vector<T>& values,size_t size) {
    values.resize(size);
    return std::fread(values.data(),sizeof(T),size,file)==size;
}

void psqt_options(OptionsMap& options) {
    options.add("EvalFile",Option("<none>",[](const Option& option) {
        psqt_path=std::string(option);psqt_loaded=false;tiny_loaded=false;halfkp_linear_loaded=false;
        tiny_output32=false;
        tiny_fc_packed32=false;
        tiny_accumulator_packed=false;
        tiny_fixed_radix=false;
        tiny_fc_pairs.clear();
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
    bool version3=ok && !std::memcmp(magic,"S95NN03\0",8);
    if(version1 || version2 || version3) {
        uint32_t header[4];
        ok=std::fread(header,4,4,file)==4
            && (version3?(header[0]==125388 && header[3]==1548):
                         ((header[0]==171720 || (version2 && header[0]==95400)) && header[3]==2120))
            && header[1]>=1 && header[1]<=32 && header[2]<=32 && (version2 || version3 || header[2]>=1);
        if(ok) {
            tiny_width=header[1];tiny_hidden=header[2];tiny_symmetric=header[0]==95400;
            tiny_standard_halfkp=version3;
            ok=read_weights(file,tiny_embedding,size_t(header[0])*tiny_width)
                && read_weights(file,tiny_bias,tiny_width)
                && read_weights(file,tiny_fc,tiny_hidden*tiny_width*2)
                && read_weights(file,tiny_fc_bias,tiny_hidden)
                && read_weights(file,tiny_out,tiny_hidden?tiny_hidden:tiny_width*2)
                && std::fread(&tiny_out_bias,4,1,file)==1;
        }
        tiny_loaded=ok;
    } else if(ok && !std::memcmp(magic,"S95HKL1\0",8)) {
        static_assert(fe_end==1548,"HalfKP linear files require the standard BonaPiece layout");
        uint32_t header[2];
        ok=std::fread(header,4,2,file)==2 && header[0]==81*1548 && header[1]==256;
        if(ok)ok=read_weights(file,halfkp_linear_weights,header[0]);
        halfkp_linear_loaded=ok;
    } else if(ok) {
        ok=!std::memcmp(magic,"S95PSQ1\0",8) && std::fread(&count,4,1,file)==1 && count==637
            && std::fread(psqt_weights.data(),2,637,file)==637;
    }
    if(ok)ok=std::fgetc(file)==EOF;
    if(file)std::fclose(file);
    if(!ok) { std::printf("info string invalid evaluation file: %s\n",psqt_path.c_str());std::fflush(stdout);std::exit(1); }
    if(tiny_loaded) {
        // Every head activation is in [0,128]. Include every possible partial
        // sum and reserve space for the final absolute-value rounding.
        int64_t low=tiny_out_bias,high=tiny_out_bias;
        for(int16_t weight:tiny_out) {
            if(weight<0)low+=int64_t(weight)*128;
            else high+=int64_t(weight)*128;
        }
        constexpr int64_t limit=int64_t(std::numeric_limits<int32_t>::max())-128;
        tiny_output32=low>=-limit && high<=limit;
        tiny_fixed_radix=tiny_standard_halfkp && tiny_output32
            && FixedRadixHead::matches(tiny_out.data(),tiny_out_bias,tiny_width,tiny_hidden);
        tiny_fc_packed32=tiny_standard_halfkp && tiny_hidden>0;
        for(unsigned i=0;i<tiny_hidden;++i) {
            int64_t fc_low=tiny_fc_bias[i],fc_high=tiny_fc_bias[i];
            for(unsigned j=0;j<tiny_width*2;++j) {
                int weight=tiny_fc[i*tiny_width*2+j];
                if(weight < -128 || weight > 127)tiny_fc_packed32=false;
                if(weight<0)fc_low+=int64_t(weight)*128;
                else fc_high+=int64_t(weight)*128;
            }
            if(fc_low<std::numeric_limits<int32_t>::min()
                || fc_high>int64_t(std::numeric_limits<int32_t>::max())-32)tiny_fc_packed32=false;
        }
        if(tiny_fc_packed32) {
            tiny_fc_pairs.resize(tiny_hidden*tiny_width);
            for(unsigned i=0;i<tiny_hidden;++i)
                for(unsigned j=0;j<tiny_width;++j) {
                    unsigned offset=i*tiny_width*2+j*2;
                    tiny_fc_pairs[i*tiny_width+j]=PackedFC::coefficients(tiny_fc[offset],tiny_fc[offset+1]);
                }
        }
        tiny_accumulator_packed=tiny_standard_halfkp && (tiny_width==8 || tiny_width==16);
        if(tiny_accumulator_packed) {
            static_assert(PIECE_NUMBER_KING==38,"packed cache bound assumes38 non-king piece slots");
            std::array<int,32> lowest{},highest{};
            for(size_t row=0;row<tiny_embedding.size();row+=tiny_width)
                for(unsigned lane=0;lane<tiny_width;++lane) {
                    int weight=tiny_embedding[row+lane];
                    lowest[lane]=std::min(lowest[lane],weight);
                    highest[lane]=std::max(highest[lane],weight);
                }
            for(unsigned lane=0;lane<tiny_width;++lane) {
                int64_t low=int64_t(tiny_bias[lane])+int64_t(PackedAccumulator::maximum_active_slots)*lowest[lane];
                int64_t high=int64_t(tiny_bias[lane])+int64_t(PackedAccumulator::maximum_active_slots)*highest[lane];
                if(low < -PackedAccumulator::bias || high>=PackedAccumulator::bias)tiny_accumulator_packed=false;
            }
            if(tiny_accumulator_packed)
                for(size_t offset=0;offset<tiny_embedding.size();offset+=2) {
                    uint32_t word=PackedAccumulator::delta(tiny_embedding[offset],tiny_embedding[offset+1]);
                    PackedAccumulator::write(tiny_embedding.data()+offset,word);
                }
        }
    }
    psqt_loaded=true;
    std::printf("info string shogi1995 %s loaded: %s\n",halfkp_linear_loaded?"HalfKP linear":tiny_loaded?"tiny network":"PSQT",psqt_path.c_str());std::fflush(stdout);
}

// Width=0 retains the general layout. Nonzero widths are dispatched only for
// standard HalfKP, so the compiler can fold both row strides and lane loops.
template<unsigned Width> void tiny_add_width(int* accumulator,int king,int feature,int count) {
    const unsigned width=Width?Width:tiny_width;
    int king_index=Width?king:(tiny_symmetric?(king%9)*5+std::min(king/9,8-king/9):king);
    const int16_t* weights=tiny_embedding.data()+size_t(king_index*((Width || tiny_standard_halfkp)?1548:2120)+feature)*width;
    if(tiny_accumulator_packed) {
        // Independent full recomputation recovers each original coefficient;
        // production packed updates use the separate word-add path below.
        for(unsigned j=0;j<width;++j)accumulator[j]+=PackedAccumulator::coefficient(weights,j)*count;
        return;
    }
    // HalfKP updates add or remove one feature. Avoid one scalar IMUL per
    // lane on the Pentium, while preserving arbitrary legacy hand counts.
    if(count==1)
        for(unsigned j=0;j<width;++j)accumulator[j]+=int(weights[j]);
    else if(count==-1)
        for(unsigned j=0;j<width;++j)accumulator[j]-=int(weights[j]);
    else
        for(unsigned j=0;j<width;++j)accumulator[j]+=int(weights[j])*count;
}

template<unsigned Width> void tiny_add_packed_width(int* accumulator,int king,int feature,int count) {
    static_assert(Width==8 || Width==16,"packed cache width must be8 or16");
    const int16_t* weights=tiny_embedding.data()+size_t(king*1548+feature)*Width;
    if(count==1)
        for(unsigned j=0;j<Width/2;++j)
            PackedAccumulator::write(accumulator+j,PackedAccumulator::read(accumulator+j)+PackedAccumulator::read(weights+j*2));
    else
        for(unsigned j=0;j<Width/2;++j)
            PackedAccumulator::write(accumulator+j,PackedAccumulator::read(accumulator+j)-PackedAccumulator::read(weights+j*2));
}

template<unsigned Width> void tiny_full_packed_width(const Position& pos,int perspective,int king,int* accumulator) {
    for(unsigned j=0;j<Width/2;++j)
        PackedAccumulator::write(accumulator+j,PackedAccumulator::encode(tiny_bias[j*2],tiny_bias[j*2+1]));
    const auto* pieces=perspective==0?pos.eval_list()->piece_list_fb():pos.eval_list()->piece_list_fw();
    for(int i=0;i<PIECE_NUMBER_KING;++i)tiny_add_packed_width<Width>(accumulator,king,int(pieces[i]),1);
}

void tiny_add(int* accumulator,int king,int feature,int count) {
    tiny_add_width<0>(accumulator,king,feature,count);
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

template<unsigned Width> void tiny_full_width(const Position& pos,int perspective,int king,int* accumulator) {
    const unsigned width=Width?Width:tiny_width;
    constexpr PieceType types[]={PAWN,LANCE,KNIGHT,SILVER,GOLD,BISHOP,ROOK};
    for(unsigned j=0;j<width;++j)accumulator[j]=tiny_bias[j];
    if(Width || tiny_standard_halfkp) {
        const auto* pieces=perspective==0?pos.eval_list()->piece_list_fb():pos.eval_list()->piece_list_fw();
        for(int i=0;i<PIECE_NUMBER_KING;++i)tiny_add_width<Width>(accumulator,king,int(pieces[i]),1);
        return;
    }
    for(int square=0;square<81;++square)
        tiny_board_change(accumulator,king,perspective,pos.piece_on(Square(square)),square,1);
    for(int color=0;color<2;++color)
        for(int pt=0;pt<7;++pt) {
            int count=hand_count(pos.hand_of(Color(color)),types[pt]);
            if(count)tiny_add(accumulator,king,2106+(color!=perspective)*7+pt,count);
        }
}

template<class Sum,unsigned Width> int tiny_correction(const int32_t* activation) {
    if(tiny_fixed_radix) {
        const int32_t output=FixedRadixHead::raw(activation);
        if(tiny_verify) {
            int64_t reference=tiny_out_bias;
            for(unsigned j=0;j<16;++j)reference+=int64_t(activation[j])*tiny_out[j];
            if(output!=reference) {
                std::printf("info string head mismatch radix=%d reference=%lld\n",output,(long long)reference);
                std::fflush(stdout);std::exit(2);
            }
            ++tiny_radix_verification_count;
        }
        return output>=0?int((output+128)/256):-int((-output+128)/256);
    }
    const unsigned width=Width?Width:tiny_width;
    Sum output=tiny_out_bias;
    if(!tiny_hidden)
        for(unsigned j=0;j<width*2;++j)output+=activation[j]*int(tiny_out[j]);
    std::array<PackedFC::Activation,32> pairs;
    if(tiny_fc_packed32)
        for(unsigned j=0;j<width;++j)pairs[j]=PackedFC::activation(activation[j*2],activation[j*2+1]);
    for(unsigned i=0;i<tiny_hidden;++i) {
        int value;
        if(tiny_fc_packed32) {
            int32_t sum=tiny_fc_bias[i];
            for(unsigned j=0;j<width;++j)sum+=PackedFC::dot(pairs[j],tiny_fc_pairs[i*width+j]);
            value=sum<=0?0:std::min(128,int((sum+32)/64));
        } else {
            int64_t sum=tiny_fc_bias[i];
            for(unsigned j=0;j<width*2;++j)sum+=int64_t(activation[j])*tiny_fc[i*width*2+j];
            value=sum<=0?0:std::min(128,int((sum+32)/64));
        }
        output+=value*int(tiny_out[i]);
    }
    return output>=0?int((output+128)/256):-int((-output+128)/256);
}

template<unsigned Width,bool Packed=false> int tiny_black_width(const Position& pos) {
    const unsigned width=Width?Width:tiny_width;
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
                std::memcpy(accumulator,previous->tiny_accumulator[perspective],(Packed?width/2:width)*sizeof(int));
                while(count) {
                    const StateInfo* change=changes[--count];
                    if(change->tiny_to<0)continue;
                    if(Width || tiny_standard_halfkp) {
                        const auto& dirty=change->dirtyPiece;
                        for(int i=0;i<dirty.dirty_num;++i) {
                            if(dirty.pieceNo[i]>=PIECE_NUMBER_KING)continue;
                            if constexpr(Packed) {
                                tiny_add_packed_width<Width>(accumulator,king,int(dirty.changed_piece[i].old_piece.from[perspective]),-1);
                                tiny_add_packed_width<Width>(accumulator,king,int(dirty.changed_piece[i].new_piece.from[perspective]),1);
                            } else {
                                tiny_add_width<Width>(accumulator,king,int(dirty.changed_piece[i].old_piece.from[perspective]),-1);
                                tiny_add_width<Width>(accumulator,king,int(dirty.changed_piece[i].new_piece.from[perspective]),1);
                            }
                        }
                        continue;
                    }
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
                if constexpr(Packed)tiny_full_packed_width<Width>(pos,perspective,king,accumulator);
                else tiny_full_width<Width>(pos,perspective,king,accumulator);
                ++tiny_refresh_count;
            }
        }
        state->tiny_generation=tiny_generation;
    }
    if(tiny_verify) {
        for(int perspective=0;perspective<2;++perspective) {
            int king=int(pos.square<KING>(Color(perspective)));
            if(perspective)king=80-king;
            // Keep verification on the general kernel, independent of the
            // specialized lane count and row-stride expressions above.
            int full[32];tiny_full_width<0>(pos,perspective,king,full);
            for(unsigned j=0;j<width;++j) {
                int cached=Packed?PackedAccumulator::lane(state->tiny_accumulator[perspective],j):state->tiny_accumulator[perspective][j];
                if(full[j]!=cached) {
                    std::printf("info string accumulator mismatch perspective=%d lane=%u cached=%d full=%d\n",
                                perspective,j,cached,full[j]);
                    std::fflush(stdout);std::exit(2);
                }
            }
        }
        ++tiny_verification_count;
    }
    int32_t activation[64];
    int stm=int(pos.side_to_move());
    for(int relative=0;relative<2;++relative) {
        if constexpr(Packed)
            for(unsigned j=0;j<width/2;++j) {
                uint32_t word=PackedAccumulator::read(state->tiny_accumulator[stm^relative]+j);
                activation[relative*width+j*2]=std::max(0,std::min(128,PackedAccumulator::low(word)));
                activation[relative*width+j*2+1]=std::max(0,std::min(128,PackedAccumulator::high(word)));
            }
        else
            for(unsigned j=0;j<width;++j)
                activation[relative*width+j]=std::max(0,std::min(128,state->tiny_accumulator[stm^relative][j]));
    }
    int correction=tiny_output32?tiny_correction<int32_t,Width>(activation):tiny_correction<int64_t,Width>(activation);
    int black=pos.state()->materialValue+(stm?-correction:correction);
    return std::max(-12000,std::min(12000,black));
}

int tiny_black(const Position& pos) {
    if(tiny_standard_halfkp) {
        if(tiny_width==8)return tiny_accumulator_packed?tiny_black_width<8,true>(pos):tiny_black_width<8>(pos);
        if(tiny_width==16)return tiny_accumulator_packed?tiny_black_width<16,true>(pos):tiny_black_width<16>(pos);
    }
    return tiny_black_width<0>(pos);
}

int psqt_black(const Position& pos) {
    if(halfkp_linear_loaded) {
        const auto* black=pos.eval_list()->piece_list_fb();
        const auto* white=pos.eval_list()->piece_list_fw();
        const auto* bw=halfkp_linear_weights.data()+int(pos.square<KING>(BLACK))*1548;
        const auto* ww=halfkp_linear_weights.data()+(80-int(pos.square<KING>(WHITE)))*1548;
        int64_t score=0;
        for(int i=0;i<PIECE_NUMBER_KING;++i)score+=int64_t(bw[black[i]])-ww[white[i]];
        int rounded=score>=0?int((score+128)/256):-int((-score+128)/256);
        return std::max(-12000,std::min(12000,rounded));
    }
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
