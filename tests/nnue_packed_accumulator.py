#!/usr/bin/env python3
"""Check the model-wide cache range guard, plain fallback and stale-cache invalidation."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

import cshogi
import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from shogi1995.halfkp_features import INPUTS,STRIDE
from shogi1995.sessions import COMMON
from shogi1995.tiny_quant import load,reference
from shogi1995.usi import Engine


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--data',required=True,type=Path);parser.add_argument('--work',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path);parser.add_argument('--width',type=int,choices=[8,16],default=8)
    args=parser.parse_args()
    if args.work.exists() or args.output.exists():raise ValueError('preserve previous attempt')
    args.work.mkdir(parents=True);width=args.width
    # First-layer bias0/bias1, embedding weight0/weight1, expected packed flag.
    cases=[('zero',0,0,0,0,1),('mixed',64,64,-1,1,1),
           ('lower-safe',-32728,64,-1,1,1),('lower-fallback',-32729,64,-1,1,0),
           ('upper-safe',32727,64,1,-1,1),('upper-fallback',32728,64,1,-1,0),
           ('minimum-bias',-32768,64,0,0,1),('below-minimum-bias',-32769,64,0,0,0),
           ('maximum-bias',32767,64,0,0,1),('above-maximum-bias',32768,64,0,0,0),
           ('wide-negative-coefficient',0,64,-32768,0,0),('wide-positive-coefficient',0,64,32767,0,0),
           ('int32-minimum-bias',-2**31,64,0,0,0),('int32-maximum-bias',2**31-1,64,0,0,0)]
    records=np.memmap(args.data,dtype=cshogi.PackedSfenValue,mode='r');board=cshogi.Board()
    sfens=[cshogi.STARTING_SFEN]
    for index in np.linspace(0,len(records)-1,15,dtype=int):board.set_psfen(records[index]['sfen']);sfens.append(board.sfen())
    binary=ROOT/'.local/guest-root/shogi';results=[];last_sfen=None;mixed=None
    with Engine([str(binary)],ROOT,args.work/'engine.logs',COMMON) as engine:
        def value(sfen,weights,send_position=True):
            board.set_sfen(sfen)
            if send_position:engine.send('position sfen '+sfen)
            engine.send('shogi1995eval');_,lines=engine.until('info string shogi1995 eval ',5)
            actual=int(lines[-1].split()[-1]);assert actual==reference(board,weights),(sfen,actual)
        def stats():
            engine.send('shogi1995evalstats');_,lines=engine.until('info string shogi1995 accumulators ',5)
            return {k:int(v) for k,v in (x.split('=') for x in lines[-1].split()[4:])}
        for name,a,b,u,v,packed in cases:
            embedding=np.tile(np.array([u,v],dtype='<i2'),(INPUTS,width//2))
            data=b'S95NN03\0'+struct.pack('<4I',INPUTS,width,0,STRIDE)+embedding.tobytes()
            data+=np.tile(np.array([a,b],dtype='<i4'),width//2).tobytes()
            data+=np.tile(np.array([256,512],dtype='<i2'),width).tobytes()+struct.pack('<i',0)
            path=args.work/(name+'.bin');path.write_bytes(data);weights=load(path)
            engine.send('setoption name EvalFile value '+str(path.resolve()));engine.reset();actual_stats=stats()
            assert actual_stats.get('accumulator_packed')==packed,(name,actual_stats)
            assert actual_stats.get('accumulator_bits')==(16 if packed else 32),(name,actual_stats)
            if last_sfen is not None:value(last_sfen,weights,False)
            for sfen in sfens:value(sfen,weights)
            last_sfen=sfens[-1]
            if name=='mixed':mixed=(path,weights)
            results.append({'case':name,'accumulator_packed':packed,'positions':len(sfens),
                            'model_sha256':hashlib.sha256(data).hexdigest()})
        engine.send('setoption name EvalFile value <none>');engine.reset()
        assert stats()['accumulator_packed']==0 and stats()['accumulator_bits']==0
        path,weights=mixed;engine.send('setoption name EvalFile value '+str(path.resolve()));engine.reset()
        value(last_sfen,weights,False)
    report={'passed':True,'width':width,'cases':results,'mixed_model_switch_without_position_reset':True,
            'disable_and_reenable_passed':True,'engine_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),
            'test_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'scope':'range-guard, integer values and cache invalidation only; not speed or strength'}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
