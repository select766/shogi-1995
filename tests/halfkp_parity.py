#!/usr/bin/env python3
"""Check standard BonaPiece features and pure-linear integer scores in the engine."""
import argparse
import json
from pathlib import Path
import sys
import cshogi
import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from shogi1995.halfkp_features import encode,INPUTS,material_initial_weights
from shogi1995.halfkp_linear import export,load,reference
from shogi1995.usi import Engine


def main():
    p=argparse.ArgumentParser();p.add_argument('--data',required=True,type=Path)
    p.add_argument('--model',type=Path);p.add_argument('--count',type=int,default=512)
    p.add_argument('--output',required=True,type=Path);args=p.parse_args()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    if args.model is None:
        rng=np.random.default_rng(20261106)
        model=args.output.with_suffix('.synthetic.bin')
        export(material_initial_weights()+rng.uniform(-12,12,INPUTS),model)
    else:model=args.model
    weights=load(model);records=np.memmap(args.data,dtype=cshogi.PackedSfenValue,mode='r')
    board=cshogi.Board();options={'Threads':1,'USI_Hash':2,'USI_OwnBook':False,'EvalFile':str(model.resolve())}
    with Engine([str(ROOT/'.local/guest-root/shogi')],ROOT,args.output.with_suffix('.logs'),options) as client:
        for index in np.linspace(0,len(records)-1,args.count,dtype=int):
            board.set_psfen(records[index]['sfen']);client.send('position sfen '+board.sfen())
            client.send('shogi1995halfkp')
            _,lines=client.until('info string shogi1995 halfkp perspective=1',5)
            actual=[list(map(int,line.split()[5:])) for line in lines if line.startswith('info string shogi1995 halfkp perspective=')]
            expected=encode(board)
            assert len(actual)==2
            for side in range(2):assert sorted(actual[side])==sorted(expected[side]),(int(index),side)
            client.send('shogi1995eval');_,lines=client.until('info string shogi1995 eval ',5)
            assert int(lines[-1].split()[-1])==reference(board,weights),(int(index),board.sfen())
    report={'passed':True,'positions':args.count,'standard_halfkp_feature_multisets_match':True,'integer_scores_match':True}
    args.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))


if __name__=='__main__':main()
