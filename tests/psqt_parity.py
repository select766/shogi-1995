#!/usr/bin/env python3
"""Compare exported quantized PSQT feature arithmetic against the real native engine."""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
import cshogi

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from shogi1995.usi import Engine

def reference(board,weights):
    score=0
    for sq,piece in enumerate(board.pieces):
        if not piece:continue
        white=piece>=16;oriented=80-sq if white else sq;file,rank=divmod(oriented,9)
        value=int(weights[((piece&15)-1)*45+rank*5+min(file,8-file)])
        score+=-value if white else value
    hands=board.pieces_in_hand
    score+=sum((hands[0][i]-hands[1][i])*int(weights[630+i]) for i in range(7))
    score=max(-12000,min(12000,score))
    return -score if board.turn else score

def main():
    p=argparse.ArgumentParser();p.add_argument('--model',required=True,type=Path);p.add_argument('--data',required=True,type=Path)
    p.add_argument('--count',type=int,default=256);args=p.parse_args()
    weights=np.frombuffer(args.model.read_bytes(),dtype='<i2',offset=12)
    rows=np.memmap(args.data,dtype=cshogi.PackedSfenValue,mode='r');b=cshogi.Board()
    options={'Threads':1,'USI_Hash':2,'USI_OwnBook':False,'EvalFile':str(args.model.resolve())}
    with Engine([str(ROOT/'.local/guest-root/shogi')],ROOT,ROOT/'.local/tests/psqt-parity',options) as e:
        for index in np.linspace(0,len(rows)-1,args.count,dtype=int):
            b.set_psfen(rows[index]['sfen']);e.send('position sfen '+b.sfen());e.send('shogi1995eval')
            _,lines=e.until('info string shogi1995 eval ',5)
            actual=int(lines[-1].split()[-1]);expected=reference(b,weights)
            assert actual==expected,(index,b.sfen(),expected,actual)
    print(json.dumps({'positions':args.count,'exact_value_matches':args.count,'passed':True}))

if __name__=='__main__':main()
