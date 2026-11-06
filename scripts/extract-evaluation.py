#!/usr/bin/env python3
"""Create the immutable, seed-fixed HCPE evaluation series from its original file."""
import argparse
from collections import Counter
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import random
import sys

import cshogi
import numpy as np

EXPECTED_SHA='fb9d60b283ade32cb5c5715fe27042476bc7169cc46b6d62a2d85975c1a945ac'
DEFAULT_INPUT='/home/select766/shogi/train-nnue/tmp/floodgate.hcpe/floodgate.hcpe'
DEFAULT_OUTPUT='/media/select766/HDCZ-UT/s7ubuntu/dev/shogi-1995/evaluation/floodgate-hcpe-1995-v1'


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        while chunk:=f.read(1024*1024):h.update(chunk)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--input',default=DEFAULT_INPUT)
    p.add_argument('--output',default=DEFAULT_OUTPUT);args=p.parse_args()
    source=Path(args.input);out=Path(args.output)
    assert digest(source)==EXPECTED_SHA,'HCPE source differs from approved revision'
    assert cshogi.HuffmanCodedPosAndEval.itemsize==38
    if out.exists() and any(out.iterdir()):raise RuntimeError('output exists; never redraw an existing series')
    out.mkdir(parents=True,exist_ok=True)
    data=np.memmap(source,dtype=cshogi.HuffmanCodedPosAndEval,mode='r')
    board=cshogi.Board();seen={};eligible=[];reasons=Counter();conflicts=0
    for i,r in enumerate(data):
        try:
            board.set_hcp(r['hcp'])
            move=board.move_from_move16(int(r['bestMove16'])&0xffff)
            if not board.is_legal(move):reasons['illegal_label']+=1;continue
            sfen=' '.join(board.sfen().split()[:3])
            label=cshogi.move_to_usi(move)
            if sfen in seen:
                reasons['duplicate_position']+=1
                if seen[sfen]!=label:conflicts+=1
                continue
            seen[sfen]=label;eligible.append(i)
        except (ValueError,RuntimeError,OverflowError):reasons['decode_error']+=1
        if i and i%100000==0:print(f'validated {i}/{len(data)}',flush=True)
    indices=random.Random(20261106).sample(eligible,5220)
    records=[]
    for i in indices:
        r=data[i];board.set_hcp(r['hcp'])
        move=board.move_from_move16(int(r['bestMove16'])&0xffff)
        records.append({'id':f'hcpe-{i}','source_index':i,'sfen':' '.join(board.sfen().split()[:3])+' 1',
                        'bestmove':cshogi.move_to_usi(move),'turn':int(board.turn),
                        'eval':int(r['eval']),'game_result':int(r['gameResult']),
                        'in_check':bool(board.is_check())})
    splits={'quick':records[:256],'development':records[:1024],
            'test':records[1024:5120],'match':records[5120:]}
    outputs={}
    for name,rows in splits.items():
        path=out/(name+'.jsonl')
        path.write_text(''.join(json.dumps(r,separators=(',',':'))+'\n' for r in rows))
        outputs[name]={'path':str(path),'count':len(rows),'sha256':digest(path)}
    excluded=out/'excluded-sfen.txt'
    excluded.write_text(''.join(' '.join(r['sfen'].split()[:3])+'\n' for r in records))
    manifest={'series':'floodgate-hcpe-1995-v1','complete':True,'seed':20261106,
              'source':str(source.resolve()),'source_sha256':EXPECTED_SHA,'source_records':len(data),
              'source_bytes':source.stat().st_size,'eligible_unique_positions':len(eligible),
              'rejections':dict(reasons),'conflicting_duplicate_labels':conflicts,
              'algorithm':'source-order legality check; first occurrence of normalized SFEN; random.Random(seed).sample(eligible_indices,5220)',
              'python':platform.python_version(),'dependencies':{n:importlib.metadata.version(n) for n in ('cshogi','numpy')},
              'extractor_sha256':digest(__file__),'outputs':outputs,
              'sample_source_indices':indices,'excluded_sfen_sha256':digest(excluded),
              'limitations':['No source game IDs or true game ply in HCPE','Intervals do not account for unknown within-game correlation']}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({k:v for k,v in manifest.items() if k!='sample_source_indices'},indent=2))


if __name__=='__main__':main()
