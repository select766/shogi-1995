#!/usr/bin/env python3
"""Test the C++ biased-cache helper against Python's independent integer sums."""
import argparse
from datetime import datetime,timezone
import hashlib
import itertools
import json
from pathlib import Path
import random
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
    if args.output.exists():raise ValueError('preserve previous evidence')
    cases=list(itertools.product((-32768,-32767,-128,-1,0,1,127,32766,32767),
                                 (-32768,-32767,-128,-1,0,1,127,32766,32767),
                                 (-32768,-256,-1,0,1,255,32767),(-32768,-256,-1,0,1,255,32767)))
    seed=20261107;rng=random.Random(seed)
    cases += [(rng.randrange(-16384,16384),rng.randrange(-16384,16384),
               rng.randrange(-8192,8192),rng.randrange(-8192,8192)) for _ in range(8192)]
    rows=[]
    for a,b,u,v in cases:
        for sign in (1,-1):
            if -32768<=a+sign*u<32768 and -32768<=b+sign*v<32768:rows.append((a,b,u,v,sign))
    source=r'''#include <cstdio>
#include "eval/material/shogi1995_packed_accumulator.h"
using namespace YaneuraOu::Eval;
int main() {
    int a,b,u,v,sign;
    while(std::scanf("%d %d %d %d %d",&a,&b,&u,&v,&sign)==5) {
        uint32_t cache=PackedAccumulator::encode(a,b),delta=PackedAccumulator::delta(u,v);
        cache=sign==1?cache+delta:cache-delta;
        int lanes[2]={};int16_t weights[2]={};
        PackedAccumulator::write(lanes,cache);PackedAccumulator::write(weights,delta);
        std::printf("%d %d %d %d %d %d\n",PackedAccumulator::low(cache),PackedAccumulator::high(cache),
            PackedAccumulator::lane(lanes,0),PackedAccumulator::lane(lanes,1),
            PackedAccumulator::coefficient(weights,0),PackedAccumulator::coefficient(weights,1));
    }
}
'''
    with tempfile.TemporaryDirectory() as folder:
        work=Path(folder);(work/'test.cpp').write_text(source)
        subprocess.run(['g++','-O2','-std=c++17','-fsanitize=undefined','-fno-sanitize-recover=all',
                        '-I',str(ROOT/'vendor/YaneuraOu/source'),str(work/'test.cpp'),'-o',str(work/'test')],check=True)
        result=subprocess.run([str(work/'test')],input=''.join(' '.join(map(str,row))+'\n' for row in rows),
                              capture_output=True,text=True,check=True)
        actual=result.stdout.splitlines();assert not result.stderr and len(actual)==len(rows)
        for row,line in zip(rows,actual):
            a,b,u,v,sign=row;x,y=a+sign*u,b+sign*v
            assert list(map(int,line.split()))==[x,y,x,y,u,v],(row,line)
    header=ROOT/'vendor/YaneuraOu/source/eval/material/shogi1995_packed_accumulator.h'
    report={'passed':True,'verified_at_utc':datetime.now(timezone.utc).isoformat(),'seed':seed,'cases':len(rows),
            'undefined_behavior_sanitizer_passed':True,'helper_sha256':hashlib.sha256(header.read_bytes()).hexdigest(),
            'test_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'scope':'native C++ helper arithmetic, storage and coefficient recovery only; not Pentium execution/speed/strength'}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
