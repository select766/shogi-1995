#!/usr/bin/env python3
"""Deterministic ordered train encoding with bounded CPU worker results."""
import argparse
from collections import Counter,deque
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime,timezone
import hashlib
import json
import multiprocessing
from pathlib import Path
import sys
import time
import cshogi
import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from shogi1995.halfkp_features import encode,INPUTS,STRIDE,ACTIVE


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        while data:=f.read(1024*1024):h.update(data)
    return h.hexdigest()


def initialize(raw,excluded,validation):
    global RECORDS,EXCLUDED,VALIDATION,BOARD
    RECORDS=np.memmap(raw,dtype=cshogi.PackedSfenValue,mode='r')
    EXCLUDED=set(Path(excluded).read_text().splitlines())
    VALIDATION=set(Path(validation).read_text().splitlines());BOARD=cshogi.Board()


def chunk(bounds):
    start,end=bounds;xs=[];ys=[];indices=[];rejections=Counter()
    for index in range(start,end):
        row=RECORDS[index]
        if int(row['move'])!=0:raise ValueError('qsearch leaf must have MOVE_NONE')
        BOARD.set_psfen(row['sfen']);pieces=BOARD.pieces
        if pieces.count(8)!=1 or pieces.count(24)!=1:raise ValueError('invalid king count')
        key=' '.join(BOARD.sfen().split()[:3])
        if key in EXCLUDED:rejections['evaluation_overlap']+=1;continue
        if key in VALIDATION:rejections['validation_overlap']+=1;continue
        if abs(int(row['score']))>=30000:rejections['mate_score']+=1;continue
        xs.append(encode(BOARD));ys.append(int(row['score']));indices.append(index)
    return (end,np.asarray(xs,dtype='<i4').tobytes(),np.asarray(ys,dtype='<f4').tobytes(),
            np.asarray(indices,dtype='<u4').tobytes(),len(xs),dict(rejections))


def main():
    p=argparse.ArgumentParser();p.add_argument('--qsearch-manifest',required=True,type=Path)
    p.add_argument('--validation',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--workers',type=int,default=4);p.add_argument('--chunk-records',type=int,default=65536)
    p.add_argument('--exclusions',type=Path,default=Path('/media/select766/HDCZ-UT/s7ubuntu/dev/shogi-1995/evaluation/floodgate-hcpe-1995-v1/excluded-sfen.txt'))
    args=p.parse_args();out=args.output.resolve()
    if out.exists():raise ValueError('output exists; preserve partial encoding')
    if min(args.workers,args.chunk_records)<=0:p.error('positive worker and chunk counts required')
    source=json.loads(args.qsearch_manifest.read_text());validation=json.loads((args.validation/'manifest.json').read_text())
    if not source['complete'] or source['options']['ApplyQSearch'] is not True or source['options']['PairedShuffle'] is not False:
        raise ValueError('complete ordinary qsearch required')
    if not validation['complete'] or validation['split']!='validation':raise ValueError('complete validation required')
    keys=args.validation/'position-keys.txt';raw=Path(source['output'])
    if digest(keys)!=validation['position_keys_sha256'] or digest(raw)!=source['output_sha256']:
        raise ValueError('source hash differs')
    n=source['output_records']
    if not 0<n<2**32 or raw.stat().st_size!=n*40:raise ValueError('invalid record count')
    out.mkdir(parents=True);started=time.monotonic()
    report={'complete':False,'split':'train','started_at_utc':datetime.now(timezone.utc).isoformat(),
            'feature_layout':'YaneuraOu HalfKP(Friend), fe_end=1548, no DISTINGUISH_GOLDS',
            'inputs':INPUTS,'stride':STRIDE,'active':ACTIVE,'features_dtype':'<i4','targets_dtype':'<f4','source_index_dtype':'<u4',
            'source_qsearch_manifest':str(args.qsearch_manifest.resolve()),'source_qsearch_manifest_sha256':digest(args.qsearch_manifest),
            'source_qsearch_output_sha256':source['output_sha256'],'validation_manifest_sha256':digest(args.validation/'manifest.json'),
            'exclusions_sha256':digest(args.exclusions),'encoder_sha256':digest(Path(__file__)),
            'feature_code_sha256':digest(ROOT/'src/shogi1995/halfkp_features.py'),'workers':args.workers,
            'chunk_records':args.chunk_records,'ordered_source_indices':True,'maximum_pending_chunks':args.workers*2}
    def save():
        temp=out/'manifest.partial';temp.write_text(json.dumps(report,indent=2)+'\n');temp.replace(out/'manifest.json')
    save();written=0;rejected=Counter();bounds=iter((i,min(i+args.chunk_records,n)) for i in range(0,n,args.chunk_records))
    (out/'position-keys.txt').write_text('')
    with (out/'features.i4').open('wb') as xf,(out/'targets.f4').open('wb') as yf,(out/'source-indices.u4').open('wb') as inf:
        with ProcessPoolExecutor(max_workers=args.workers,mp_context=multiprocessing.get_context('fork'),
                initializer=initialize,initargs=(str(raw),str(args.exclusions),str(keys))) as pool:
            pending=deque()
            for _ in range(args.workers*2):
                item=next(bounds,None)
                if item is not None:pending.append(pool.submit(chunk,item))
            while pending:
                end,x,y,indices,count,counts=pending.popleft().result()
                xf.write(x);yf.write(y);inf.write(indices);written+=count;rejected.update(counts)
                report.update(processed=end,records=written,rejections=dict(rejected),elapsed_seconds=time.monotonic()-started);save()
                print(json.dumps({k:report[k] for k in ['processed','records','elapsed_seconds']}),flush=True)
                item=next(bounds,None)
                if item is not None:pending.append(pool.submit(chunk,item))
    if not written:raise ValueError('no usable leaves')
    report.update(complete=True,features_sha256=digest(out/'features.i4'),targets_sha256=digest(out/'targets.f4'),
                  source_indices_sha256=digest(out/'source-indices.u4'),position_keys_sha256=digest(out/'position-keys.txt'),
                  finished_at_utc=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-started)
    save();print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':main()
