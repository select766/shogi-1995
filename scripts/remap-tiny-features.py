#!/usr/bin/env python3
"""Canonicalize this project's fresh feature cache with complete provenance."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from shogi1995.tiny_features import canonicalize, INPUTS, SYMMETRIC_INPUTS, STRIDE, ACTIVE


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        while chunk:=f.read(1024*1024):h.update(chunk)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--data',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    args=p.parse_args()
    if args.output.exists():raise ValueError('output exists')
    source=json.loads((args.data/'manifest.json').read_text())
    if not source['complete'] or source['inputs']!=INPUTS:raise ValueError('expected immutable full-king features')
    args.output.mkdir(parents=True);started=time.monotonic()
    report={'complete':False,'feature_layout':'canonical-halfking','inputs':SYMMETRIC_INPUTS,'stride':STRIDE,'active':ACTIVE,
            'source_feature_manifest_sha256':digest(args.data/'manifest.json'),
            'source_manifest_sha256':source['source_manifest_sha256'],
            'remapper_sha256':digest(Path(__file__)),
            'encoder_sha256':digest(ROOT/'src/shogi1995/tiny_features.py'),'splits':{}}
    for split in ('train','validation'):
        for kind in ('features','targets'):
            if digest(args.data/f'{split}-{kind}.npy')!=source['splits'][split][kind+'_sha256']:
                raise ValueError('source feature hash differs')
        x=np.load(args.data/f'{split}-features.npy',mmap_mode='r')
        y=np.lib.format.open_memmap(args.output/f'{split}-features.npy',mode='w+',dtype='<i4',shape=x.shape)
        for start in range(0,len(x),32768):
            y[start:start+32768]=canonicalize(x[start:start+32768])
            if start%1048576==0:print(split,start,'/',len(x),flush=True)
        y.flush();shutil.copyfile(args.data/f'{split}-targets.npy',args.output/f'{split}-targets.npy')
        report['splits'][split]={'records':len(x),'features_sha256':digest(args.output/f'{split}-features.npy'),
                                'targets_sha256':digest(args.output/f'{split}-targets.npy')}
    report.update(complete=True,elapsed_seconds=time.monotonic()-started)
    (args.output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
