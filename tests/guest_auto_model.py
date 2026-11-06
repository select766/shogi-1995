#!/usr/bin/env python3
"""Exercise a prepared launcher without sending EvalFile from the client."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys
import cshogi
import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from shogi1995.usi import Engine
from shogi1995.sessions import COMMON,digest
from shogi1995.tiny_quant import load,reference


def main():
    p=argparse.ArgumentParser();p.add_argument('--profile',required=True,type=Path)
    p.add_argument('--data',required=True,type=Path);p.add_argument('--output',required=True,type=Path);args=p.parse_args()
    if args.output.exists():raise ValueError('output exists')
    profile=args.profile.resolve();m=json.loads((profile/'manifest.json').read_text())
    assert digest(profile/'root.ext2')==m['image_sha256']
    assert digest(profile/'model.bin')==m['model_sha256']
    weights=load(profile/'model.bin');records=np.memmap(args.data,dtype=cshogi.PackedSfenValue,mode='r');board=cshogi.Board()
    started=datetime.now(timezone.utc).isoformat()
    with Engine([str(profile/'run.sh')],ROOT,args.output.with_suffix('.logs'),COMMON) as engine:
        def value(name):
            engine.send('getoption '+name);_,lines=engine.until('Options['+name+']',10)
            return lines[-1].split('=',1)[1].strip()
        assert value('EvalFile')==m['configured_guest_options']['EvalFile']
        engine.send('setoption name EvalFile value <none>')
        assert value('EvalFile')==m['configured_guest_options']['EvalFile']
        engine.send('setoption name NetworkDelay value 234');engine.send('setoption name NetworkDelay2 value 567')
        engine.reset();assert value('NetworkDelay')=='234' and value('NetworkDelay2')=='567'
        for index in np.linspace(0,len(records)-1,16,dtype=int):
            board.set_psfen(records[index]['sfen']);engine.send('position sfen '+board.sfen());engine.send('shogi1995eval')
            _,lines=engine.until('info string shogi1995 eval ',10)
            assert int(lines[-1].split()[-1])==reference(board,weights),int(index)
        engine.send('shogi1995stats');_,lines=engine.until('info string shogi1995 memory ',10)
        memory={k:int(v) for k,v in (x.split('=') for x in lines[-1].split()[4:])}
        assert memory['swap']==0 and memory['total']<=32*1024*1024
    result={'passed':True,'started_at_utc':started,'finished_at_utc':datetime.now(timezone.utc).isoformat(),
            'positions':16,'automatic_model_selection':True,'model_cannot_be_silently_disabled':True,
            'network_delays_remain_configurable':True,'guest_memory':memory,
            'engine_sha256':m['engine_sha256'],'model_sha256':m['model_sha256'],'image_sha256':m['image_sha256'],
            'scope':'guest USI/configuration test; not a strength measurement or ShogiHome GUI test'}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
