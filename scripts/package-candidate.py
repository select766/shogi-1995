#!/usr/bin/env python3
"""Freeze an experimental engine image without changing the default or baseline image."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from shogi1995.provenance import source_identity

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        while b:=f.read(1024*1024):h.update(b)
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--name',required=True);p.add_argument('--model',required=True,type=Path)
    p.add_argument('--feature-difference',default='変更点未記入（要追記）')
    args=p.parse_args()
    if not args.name.replace('-','').replace('_','').isalnum():raise ValueError('invalid candidate ID')
    out=ROOT/'.local/candidates'/args.name
    if out.exists():raise RuntimeError('candidate already exists; choose a new version')
    out.mkdir(parents=True)
    model=ROOT/'.local/guest-root/eval/model.bin';model.parent.mkdir(exist_ok=True)
    shutil.copyfile(args.model,model)
    shutil.copy2(ROOT/'.local/guest-root/shogi',out/'shogi')
    shutil.copyfile(args.model,out/'model.bin')
    subprocess.run(['bash','scripts/build-guest-probe.sh','--engine',str(out/'root.ext2')],cwd=ROOT,check=True)
    report={'id':args.name,'complete':True,'guest_diagnostics':True,'search_diagnostics':True,'engine_sha256':sha(out/'shogi'),'image_sha256':sha(out/'root.ext2'),
            'model_sha256':sha(out/'model.bin'),'model_bytes':(out/'model.bin').stat().st_size,
            **source_identity(),'model_origin':str(args.model.resolve()),'feature_difference':args.feature_difference,
            'engine_options':{'EvalFile':'/eval/model.bin'},
            'command':[str(ROOT/'run-shogi-1995.sh'),'--image',str(out/'root.ext2')]}
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
