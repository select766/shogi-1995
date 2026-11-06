#!/usr/bin/env python3
"""Verify packed hidden sums, clipping, rounding, range fallback and model switching."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

import cshogi
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from shogi1995.halfkp_features import INPUTS,STRIDE
from shogi1995.sessions import COMMON
from shogi1995.tiny_quant import load,reference
from shogi1995.usi import Engine


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--data',required=True,type=Path)
    parser.add_argument('--work',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--width',type=int,choices=[2,8,16,32],default=8)
    args=parser.parse_args()
    if args.work.exists() or args.output.exists():raise ValueError('preserve previous attempt')
    args.work.mkdir(parents=True)
    maximum,minimum=2**31-1,-2**31
    # name,a,b,u,v,bias,expected packed flag. Bounds cover every possible
    # activation, not only the constants selected in this synthetic model.
    cases=[('zero',0,0,0,0,0,1),('balanced',128,127,127,-128,32,1),
           ('negative-endpoint',128,128,-128,127,0,1),('positive-endpoint',128,0,127,-128,0,1),
           ('round31',1,1,1,-1,31,1),('round32',1,1,1,-1,32,1),
           ('round95',1,1,1,-1,95,1),('round96',1,1,1,-1,96,1),
           ('clip127',0,128,0,0,8159,1),('clip128',128,0,0,0,8160,1),
           ('coefficient128',1,0,128,0,0,0),('coefficient-minus129',1,0,-129,0,256,0),
           ('positive-safe',128,0,1,0,maximum-32-128,1),
           ('positive-overflow-fallback',128,0,1,0,maximum-32-127,0),
           ('negative-safe',128,0,-128,0,minimum+16384,1),
           ('negative-overflow-fallback',128,0,-128,0,minimum+16383,0),
           ('maximum-bias',0,0,0,0,maximum,0),('minimum-bias',0,0,0,0,minimum,1)]
    records=np.memmap(args.data,dtype=cshogi.PackedSfenValue,mode='r')
    indices=np.linspace(0,len(records)-1,16,dtype=int);board=cshogi.Board()
    binary=ROOT/'.local/guest-root/shogi';rows=[]
    with Engine([str(binary)],ROOT,args.work/'engine.logs',COMMON) as engine:
        for name,a,b,u,v,bias,packed in cases:
            width=args.width;hidden=1
            model=b'S95NN03\0'+struct.pack('<4I',INPUTS,width,hidden,STRIDE)
            model+=np.zeros((INPUTS,width),dtype='<i2').tobytes()
            model+=np.tile(np.array([a,b],dtype='<i4'),width//2).tobytes()
            fc=np.zeros(width*2,dtype='<i2');fc[:2]=u,v
            model+=fc.tobytes()+struct.pack('<i',bias)+struct.pack('<h',256)+struct.pack('<i',0)
            path=args.work/(name+'.bin');path.write_bytes(model);weights=load(path)
            engine.send('setoption name EvalFile value '+str(path.resolve()));engine.reset()
            engine.send('shogi1995evalstats');_,lines=engine.until('info string shogi1995 accumulators ',5)
            stats={k:int(v) for k,v in (x.split('=') for x in lines[-1].split()[4:])}
            assert stats.get('fc_packed')==packed,(name,stats)
            assert stats.get('fc_bits')==(32 if packed else 64),(name,stats)
            for index in indices:
                board.set_psfen(records[index]['sfen']);engine.send('position sfen '+board.sfen())
                engine.send('shogi1995eval');_,lines=engine.until('info string shogi1995 eval ',5)
                actual=int(lines[-1].split()[-1]);assert actual==reference(board,weights),(name,index,actual)
            rows.append({'case':name,'fc_packed':packed,'positions':len(indices),
                         'model_sha256':hashlib.sha256(model).hexdigest()})
        engine.send('setoption name EvalFile value <none>');engine.reset()
        engine.send('shogi1995evalstats');_,lines=engine.until('info string shogi1995 accumulators ',5)
        stats={k:int(v) for k,v in (x.split('=') for x in lines[-1].split()[4:])}
        assert stats.get('fc_packed')==0 and stats.get('fc_bits')==0,stats
    result={'passed':True,'width':args.width,'cases':rows,'model_switch_and_disable_passed':True,
            'engine_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),
            'test_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'scope':'integer range, rounding and model-switch validation; not speed or strength'}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
