#!/usr/bin/env python3
"""Study two biased signed16 accumulator lanes with one scalar unsigned32 add."""
import argparse
from array import array
from datetime import datetime, timezone
import hashlib
import itertools
import json
from pathlib import Path
import random
import struct
import sys

BIAS=32768
MASK=(1<<32)-1


def pack(a,b):
    if not (-BIAS<=a<BIAS and -BIAS<=b<BIAS):raise ValueError('cache lane out of range')
    return (a+BIAS)|((b+BIAS)<<16)


def unpack(value):return (value&65535)-BIAS,(value>>16)-BIAS


def delta(u,v):
    if not (-BIAS<=u<BIAS and -BIAS<=v<BIAS):raise ValueError('coefficient out of range')
    # Sign-extending the lower coefficient adjusts the high lane by minus1
    # when u is negative; the in-range low-lane add cancels that borrow.
    return (u+(v<<16))&MASK


def signed16(value):return (value&32767)-(value&32768)


def unpack_delta(value):
    low=signed16(value&65535)
    return low,signed16(((value>>16)+(low<0))&65535)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--model',required=True,type=Path,action='append')
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--seed',type=int,default=20261107)
    args=parser.parse_args()
    if args.output.exists():raise ValueError('preserve previous study')
    rng=random.Random(args.seed);add_cases=subtract_cases=0
    cases=list(itertools.product((-32768,-32767,-128,-1,0,1,127,32766,32767),
                                 (-32768,-32767,-128,-1,0,1,127,32766,32767),
                                 (-32768,-256,-1,0,1,255,32767),(-32768,-256,-1,0,1,255,32767)))
    cases += [(rng.randrange(-16384,16384),rng.randrange(-16384,16384),
               rng.randrange(-8192,8192),rng.randrange(-8192,8192)) for _ in range(8192)]
    for a,b,u,v in cases:
        assert unpack_delta(delta(u,v))==(u,v)
        if -BIAS<=a+u<BIAS and -BIAS<=b+v<BIAS:
            assert unpack((pack(a,b)+delta(u,v))&MASK)==(a+u,b+v);add_cases+=1
        if -BIAS<=a-u<BIAS and -BIAS<=b-v<BIAS:
            assert unpack((pack(a,b)-delta(u,v))&MASK)==(a-u,b-v);subtract_cases+=1
    rejected=0
    for a,b in [(-32769,0),(32768,0),(0,-32769),(0,32768)]:
        try:pack(a,b)
        except ValueError:rejected+=1
        else:raise AssertionError('out-of-range cache lane accepted')
    models=[]
    for path in args.model:
        with path.open('rb') as file:
            if file.read(8)!=b'S95NN03\0':raise ValueError('standard HalfKP network required')
            inputs,width,hidden,stride=struct.unpack('<4I',file.read(16))
            if inputs!=125388 or stride!=1548 or width not in (8,16):raise ValueError('width8/16 model required')
            embedding=array('h');embedding.frombytes(file.read(inputs*width*2))
            if sys.byteorder!='little':embedding.byteswap()
            biases=struct.unpack('<'+'i'*width,file.read(width*4))
        # A standard HalfKP view has38 active piece slots. Reserve two more
        # slots for a conservative bound on intermediate incremental updates.
        bounds=[]
        for lane in range(width):
            weights=embedding[lane::width]
            bounds.append([biases[lane]+40*min(0,min(weights)),biases[lane]+40*max(0,max(weights))])
        applicable=all(-BIAS<=low and high<BIAS for low,high in bounds)
        sampled_pairs=0;refreshes=updates=0
        for _ in range(1024):
            offset=rng.randrange(inputs)*(width)+rng.randrange(width//2)*2
            u,v=embedding[offset:offset+2];assert unpack_delta(delta(u,v))==(u,v);sampled_pairs+=1
        if applicable:
            for _ in range(16):
                active=[rng.randrange(inputs) for _ in range(38)]
                raw=list(biases);packed=[pack(biases[j],biases[j+1]) for j in range(0,width,2)]
                for index in active:
                    for lane in range(0,width,2):
                        u,v=embedding[index*width+lane:index*width+lane+2]
                        raw[lane]+=u;raw[lane+1]+=v;packed[lane//2]=(packed[lane//2]+delta(u,v))&MASK
                        assert unpack(packed[lane//2])==(raw[lane],raw[lane+1])
                refreshes+=1
                for _ in range(32):
                    slot=rng.randrange(38);old=active[slot];new=rng.randrange(inputs);active[slot]=new
                    for index,sign in [(old,-1),(new,1)]:
                        for lane in range(0,width,2):
                            u,v=embedding[index*width+lane:index*width+lane+2]
                            raw[lane]+=sign*u;raw[lane+1]+=sign*v
                            packed[lane//2]=(packed[lane//2]+sign*delta(u,v))&MASK
                            assert unpack(packed[lane//2])==(raw[lane],raw[lane+1])
                    expected=[biases[lane]+sum(embedding[i*width+lane] for i in active) for lane in range(width)]
                    assert raw==expected;updates+=1
        models.append({'path':str(path.resolve()),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                       'width':width,'hidden':hidden,'accumulator_lane_bounds_40slots':bounds,
                       'applicable':applicable,'coefficient_roundtrips':sampled_pairs,
                       'refresh_vectors':refreshes,'incremental_vectors':updates})
    report={'passed':True,'verified_at_utc':datetime.now(timezone.utc).isoformat(),'seed':args.seed,
            'add_cases':add_cases,'subtract_cases':subtract_cases,'invalid_cache_lanes_rejected':rejected,
            'models':models,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'scope':'arbitrary-precision arithmetic and model bounds study only; no C++ runtime implementation, Pentium execution, speed or strength result',
            'condition':'Both lanes, including intermediate updates, remain in signed16 range; otherwise retain the signed32 accumulator runtime.',
            'storage_proposal':'encode existing adjacent embedding coefficients in place as unsigned32 deltas; recover each original signed16 coefficient for independent recomputation; model file unchanged',
            'guest_engine_changed':False,'model_weights_changed':False}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':True,'add_cases':add_cases,'subtract_cases':subtract_cases,
                      'models':[(m['width'],m['hidden'],m['applicable']) for m in models]}))


if __name__=='__main__':main()
