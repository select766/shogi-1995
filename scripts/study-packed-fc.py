#!/usr/bin/env python3
"""Arithmetic feasibility study only; does not change the guest engine."""
import argparse
from datetime import datetime,timezone
import hashlib
import itertools
import json
from pathlib import Path
import random
import struct
import subprocess


def pair_dot(a,b,u,v):
    if not (0<=a<=128 and 0<=b<=128 and -128<=u<=127 and -128<=v<=127):
        raise ValueError('packed pair preconditions failed')
    activation=a+(b<<16)
    weights=(v+128)+((u+128)<<16)
    product=(activation*weights)&0xffffffff
    return (product>>16)-128*(a+b)


def main():
    p=argparse.ArgumentParser();p.add_argument('--model',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path);p.add_argument('--seed',type=int,default=20261106)
    args=p.parse_args()
    if args.output.exists():raise ValueError('preserve previous study')
    with args.model.open('rb') as file:
        if file.read(8)!=b'S95NN03\0':raise ValueError('standard HalfKP network required')
        inputs,width,hidden,stride=struct.unpack('<4I',file.read(16))
        if inputs!=125388 or stride!=1548 or not 1<=width<=32 or not 1<=hidden<=32:
            raise ValueError('expected supported network with a hidden layer')
        file.seek(inputs*width*2+width*4,1)
        fc=list(struct.unpack('<'+str(hidden*2*width)+'h',file.read(hidden*2*width*2)))
        bias=list(struct.unpack('<'+str(hidden)+'i',file.read(hidden*4)))
    rows=[fc[i*2*width:(i+1)*2*width] for i in range(hidden)]
    bounds=[(bias[i]+128*sum(w for w in row if w<0),bias[i]+128*sum(w for w in row if w>0))
            for i,row in enumerate(rows)]
    applicable=all(-128<=w<=127 for w in fc) and all(-2**31<=lo and hi<=2**31-1-32 for lo,hi in bounds)
    # Base=65536. The low product and middle coefficient cannot carry into
    # the next lane: 128*255=32640 and 2*128*255=65280 are both below base.
    assert 128*255<2**16 and 2*128*255<2**16
    rng=random.Random(args.seed);cases=0
    for a,b,u,v in itertools.product((0,1,63,64,127,128),(0,1,63,64,127,128),
                                   (-128,-127,-1,0,1,126,127),(-128,-127,-1,0,1,126,127)):
        assert pair_dot(a,b,u,v)==a*u+b*v;cases+=1
    for _ in range(8192):
        a,b=rng.randrange(129),rng.randrange(129);u,v=rng.randrange(-128,128),rng.randrange(-128,128)
        assert pair_dot(a,b,u,v)==a*u+b*v;cases+=1
    for invalid in ((-1,0,0,0),(129,0,0,0),(0,0,-129,0),(0,0,128,0)):
        try:pair_dot(*invalid)
        except ValueError:pass
        else:raise AssertionError('invalid pair accepted')
    vectors=[[0]*(2*width),[128]*(2*width),[0,128]*width,[128,0]*width]
    vectors += [[rng.randrange(129) for _ in range(2*width)] for _ in range(256)]
    verified_dots=0
    if applicable:
        for activation in vectors:
            for i,weights in enumerate(rows):
                scalar=bias[i]+sum(a*w for a,w in zip(activation,weights))
                packed=bias[i]+sum(pair_dot(activation[j],activation[j+1],weights[j],weights[j+1])
                                   for j in range(0,2*width,2))
                assert packed==scalar;verified_dots+=1
    result={'measured_at_utc':datetime.now(timezone.utc).isoformat(),
            'commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
            'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'scope':'integer arithmetic feasibility; no C++ implementation, target instruction proof, speed or strength claim',
            'seed':args.seed,'pair_cases':cases,'pair_exact':True,'invalid_inputs_rejected':4,
            'max_low_product':128*255,'max_middle_coefficient':2*128*255,'lane_base':2**16,
            'model_sha256':hashlib.sha256(args.model.read_bytes()).hexdigest(),'width':width,'hidden':hidden,
            'fc_min':min(fc),'fc_max':max(fc),'bias_min':min(bias),'bias_max':max(bias),
            'fc_all_int8':all(-128<=w<=127 for w in fc),'fc_partial_sum_bounds':bounds,
            'applicable_to_model':applicable,'activation_vectors':len(vectors),'verified_model_dots':verified_dots,
            'guest_engine_changed':False,'model_weights_changed':False}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
