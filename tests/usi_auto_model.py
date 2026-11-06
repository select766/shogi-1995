#!/usr/bin/env python3
"""Validate automatic model selection and independently configurable network delays."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import shutil
import cshogi
import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from shogi1995.usi import Engine
from shogi1995.tiny_quant import load,reference


def main():
    p=argparse.ArgumentParser();p.add_argument('--model',required=True,type=Path)
    p.add_argument('--binary',required=True,type=Path);p.add_argument('--data',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path);args=p.parse_args()
    if args.output.exists():raise ValueError('output exists')
    model=args.model.resolve();binary=args.binary.resolve();weights=load(model)
    records=np.memmap(args.data,dtype=cshogi.PackedSfenValue,mode='r');board=cshogi.Board()
    options={'Threads':1,'USI_Hash':2,'USI_OwnBook':False,'NetworkDelay':0,'NetworkDelay2':0}
    with tempfile.TemporaryDirectory(prefix='shogi-auto-model-') as directory:
        cwd=Path(directory);(cwd/'engine_options.txt').write_text('EvalFile '+str(model)+'\n')
        # Upstream resolves its working directory from the executable location.
        temporary_binary=cwd/'shogi';shutil.copy2(binary,temporary_binary)
        with Engine([str(temporary_binary)],cwd,args.output.with_suffix('.logs').resolve(),options) as engine:
            def value(name):
                engine.send('getoption '+name);_,lines=engine.until('Options['+name+']',5)
                return lines[-1].split('=',1)[1].strip()
            assert value('EvalFile')==str(model)
            engine.send('setoption name EvalFile value <none>')
            assert value('EvalFile')==str(model)
            engine.send('setoption name NetworkDelay value 234')
            engine.send('setoption name NetworkDelay2 value 567')
            engine.reset()
            assert value('NetworkDelay')=='234' and value('NetworkDelay2')=='567'
            for index in np.linspace(0,len(records)-1,256,dtype=int):
                board.set_psfen(records[index]['sfen']);engine.send('position sfen '+board.sfen());engine.send('shogi1995eval')
                _,lines=engine.until('info string shogi1995 eval ',5)
                assert int(lines[-1].split()[-1])==reference(board,weights),int(index)
    result={'passed':True,'positions':256,'automatic_model_selection':True,
            'gui_default_cannot_disable_preset_model':True,'network_delays_remain_configurable':True,
            'engine_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'model_sha256':hashlib.sha256(model.read_bytes()).hexdigest(),
            'scope':'native configuration-file behavior; prepared guest image requires separate USI validation'}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
