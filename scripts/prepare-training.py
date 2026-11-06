#!/usr/bin/env python3
"""Sample contiguous source blocks from approved PSV files, with held-out files and SFEN exclusions."""
import argparse
import bisect
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import random
import time
import sys

import cshogi
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from shogi1995.packed import psv_move_usi

SOURCE=Path('/media/select766/HDCZ-UT/s7ubuntu/dev/train-nnue/dataset/tanuki-.nnue-pytorch-2024-07-30.1')
EVALUATION=Path('/media/select766/HDCZ-UT/s7ubuntu/dev/shogi-1995/evaluation/floodgate-hcpe-1995-v1')


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        while x:=f.read(1024*1024):h.update(x)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path)
    p.add_argument('--train-records',type=int,default=2000000);p.add_argument('--validation-records',type=int,default=32768)
    p.add_argument('--block-size',type=int,default=4096);args=p.parse_args()
    if args.output.exists() and any(args.output.iterdir()):raise RuntimeError('output exists')
    args.output.mkdir(parents=True,exist_ok=True)
    assert cshogi.PackedSfenValue.itemsize==40
    files=sorted(SOURCE.glob('*.bin'))
    order=sorted(files,key=lambda f:hashlib.sha256(('shogi1995-train-v1:'+f.name).encode()).digest())
    validation_files=order[:32];training_files=order[32:]
    exclusion_path=EVALUATION/'excluded-sfen.txt'
    excluded=set(exclusion_path.read_text().splitlines());validation_keys=set()
    manifest={'series':'tanuki-original-blocks-v2','complete':False,'seed':20261106,
              'move_codec':'YaneuraOu Move16: drop=bit14, promotion=bit15; not HCPE/Apery Move16',
              'source':str(SOURCE),'source_readme_sha256':sha(SOURCE/'README.md'),
              'exclusions_sha256':sha(exclusion_path),'block_size':args.block_size,
              'validation_files':[f.name for f in validation_files],
              'training_file_count':len(training_files),'blocks':[],'outputs':{}}
    board=cshogi.Board();started=time.monotonic()
    for split,pool,target in [('validation',validation_files,args.validation_records),('train',training_files,args.train_records)]:
        cumulative=[];total=0
        for f in pool:
            count=f.stat().st_size//40//args.block_size
            total+=count;cumulative.append(total)
        rng=random.Random(20261106+(split=='train'));used=set();rejected=Counter();written=0
        output=args.output/(split+'.bin')
        with output.open('wb') as dest:
            while written<target:
                block=rng.randrange(total)
                if block in used:continue
                used.add(block);i=bisect.bisect_right(cumulative,block)
                local_block=block-(cumulative[i-1] if i else 0);f=pool[i];offset=local_block*args.block_size*40
                with f.open('rb') as raw:
                    raw.seek(offset);contents=raw.read(args.block_size*40)
                manifest['blocks'].append({'split':split,'file':f.name,'source_size':f.stat().st_size,
                    'offset':offset,'bytes':len(contents),'sha256':hashlib.sha256(contents).hexdigest()})
                records=np.frombuffer(contents,dtype=cshogi.PackedSfenValue)
                for r in records:
                    if written>=target:break
                    if abs(int(r['score']))>=30000:rejected['mate_score']+=1;continue
                    try:
                        board.set_psfen(r['sfen'])
                        move=board.move_from_usi(psv_move_usi(int(r['move'])))
                        if not board.is_legal(move):rejected['illegal_label']+=1;continue
                        key=' '.join(board.sfen().split()[:3])
                    except (RuntimeError,ValueError,OverflowError):rejected['decode_error']+=1;continue
                    if key in excluded:rejected['evaluation_overlap']+=1;continue
                    if key in validation_keys:rejected['validation_overlap_or_duplicate']+=1;continue
                    if split=='validation':validation_keys.add(key)
                    dest.write(r.tobytes());written+=1
                if len(used)%10==0:print(f'{split}: {written}/{target}, blocks={len(used)}',flush=True)
        manifest['outputs'][split]={'file':str(output),'records':written,'sha256':sha(output),'rejections':dict(rejected)}
        (args.output/'manifest.partial.json').write_text(json.dumps(manifest,indent=2)+'\n')
    manifest['complete']=True;manifest['elapsed_seconds']=time.monotonic()-started
    manifest['extractor_sha256']=sha(__file__)
    (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({k:v for k,v in manifest.items() if k!='blocks'},indent=2))


if __name__=='__main__':main()
