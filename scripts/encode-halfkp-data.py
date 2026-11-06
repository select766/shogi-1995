#!/usr/bin/env python3
"""Encode fresh qsearch leaves, excluding frozen evaluation and validation positions."""
import argparse
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
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


def main():
    p=argparse.ArgumentParser();p.add_argument('--qsearch-manifest',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path);p.add_argument('--split',choices=['train','validation'],required=True)
    p.add_argument('--validation',type=Path,help='Encoded held-out validation directory, required for train')
    p.add_argument('--exclusions',type=Path,default=Path('/media/select766/HDCZ-UT/s7ubuntu/dev/shogi-1995/evaluation/floodgate-hcpe-1995-v1/excluded-sfen.txt'))
    args=p.parse_args()
    if args.output.exists():raise ValueError('output exists; preserve partial encoding')
    if (args.split=='train') != (args.validation is not None):p.error('train requires --validation; validation must omit it')
    source=json.loads(args.qsearch_manifest.read_text())
    if not source['complete'] or source['options']['ApplyQSearch'] is not True or source['options']['PairedShuffle'] is not False:
        raise ValueError('complete ordinary qsearch data required')
    raw=Path(source['output'])
    if digest(raw)!=source['output_sha256']:raise ValueError('qsearch output hash differs')
    excluded=set(args.exclusions.read_text().splitlines());validation=set();seen=set()
    if args.validation:
        validation_manifest=json.loads((args.validation/'manifest.json').read_text())
        if not validation_manifest['complete'] or validation_manifest['split']!='validation':raise ValueError('validation incomplete')
        keys=args.validation/'position-keys.txt'
        if digest(keys)!=validation_manifest['position_keys_sha256']:raise ValueError('validation keys differ')
        validation=set(keys.read_text().splitlines())
    out=args.output;out.mkdir(parents=True)
    report={'complete':False,'split':args.split,'started_at_utc':datetime.now(timezone.utc).isoformat(),
            'feature_layout':'YaneuraOu HalfKP(Friend), fe_end=1548, no DISTINGUISH_GOLDS',
            'inputs':INPUTS,'stride':STRIDE,'active':ACTIVE,'features_dtype':'<i4','targets_dtype':'<f4',
            'source_index_dtype':'<u4','source_qsearch_manifest':str(args.qsearch_manifest.resolve()),
            'source_qsearch_manifest_sha256':digest(args.qsearch_manifest),'source_qsearch_output_sha256':source['output_sha256'],
            'exclusions_sha256':digest(args.exclusions),'encoder_sha256':digest(Path(__file__)),
            'feature_code_sha256':digest(ROOT/'src/shogi1995/halfkp_features.py')}
    if args.validation:report['validation_manifest_sha256']=digest(args.validation/'manifest.json')
    def save():
        p=out/'manifest.partial';p.write_text(json.dumps(report,indent=2)+'\n');p.replace(out/'manifest.json')
    save();started=time.monotonic();board=cshogi.Board();rejections=Counter();written=0
    records=np.memmap(raw,dtype=cshogi.PackedSfenValue,mode='r')
    if len(records)!=source['output_records'] or len(records)>=2**32:raise ValueError('invalid record count')
    with (out/'features.i4').open('wb') as xf,(out/'targets.f4').open('wb') as yf,(out/'source-indices.u4').open('wb') as inf,(out/'position-keys.txt').open('w') as kf:
        for start in range(0,len(records),4096):
            xs=[];ys=[];indices=[]
            for index in range(start,min(start+4096,len(records))):
                row=records[index]
                if int(row['move'])!=0:raise ValueError('qsearch leaves must have MOVE_NONE')
                board.set_psfen(row['sfen'])
                if board.pieces.count(8)!=1 or board.pieces.count(24)!=1:raise ValueError('invalid king count')
                key=' '.join(board.sfen().split()[:3])
                if key in excluded:rejections['evaluation_overlap']+=1;continue
                if key in validation:rejections['validation_overlap']+=1;continue
                if args.split=='validation' and key in seen:rejections['validation_duplicate']+=1;continue
                if abs(int(row['score']))>=30000:rejections['mate_score']+=1;continue
                xs.append(encode(board));ys.append(int(row['score']));indices.append(index)
                if args.split=='validation':seen.add(key);kf.write(key+'\n')
            if xs:
                xf.write(np.asarray(xs,dtype='<i4').tobytes());yf.write(np.asarray(ys,dtype='<f4').tobytes())
                inf.write(np.asarray(indices,dtype='<u4').tobytes());written+=len(xs)
            if start//4096%100==0:
                report.update(processed=min(start+4096,len(records)),records=written,rejections=dict(rejections));save()
                print(json.dumps({'processed':report['processed'],'total':len(records),'accepted':written}),flush=True)
    if not written:raise ValueError('no usable leaves')
    report.update(complete=True,processed=len(records),records=written,rejections=dict(rejections),
                  features_sha256=digest(out/'features.i4'),targets_sha256=digest(out/'targets.f4'),
                  source_indices_sha256=digest(out/'source-indices.u4'),position_keys_sha256=digest(out/'position-keys.txt'),
                  finished_at_utc=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-started)
    save();print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':main()
