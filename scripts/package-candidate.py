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
    p=argparse.ArgumentParser();p.add_argument('--name',required=True)
    kind=p.add_mutually_exclusive_group(required=True)
    kind.add_argument('--model',type=Path);kind.add_argument('--material',action='store_true')
    p.add_argument('--feature-difference',default='変更点未記入（要追記）')
    args=p.parse_args()
    if not args.name.replace('-','').replace('_','').isalnum():raise ValueError('invalid candidate ID')
    build_path=ROOT/'.local/last-engine-build.json'
    if not build_path.exists():raise RuntimeError('build the engine first to record its compile inputs')
    build=json.loads(build_path.read_text());identity=source_identity()
    if build['engine_sha256']!=sha(ROOT/'.local/guest-root/shogi') or build['source_tree_sha256']!=identity['source_tree_sha256']:
        raise RuntimeError('engine build does not match current sources; rebuild before packaging')
    if args.material and (ROOT/'.local/guest-root/engine_options.txt').exists():
        raise RuntimeError('material snapshot requires staging without an automatic model override')
    out=ROOT/'.local/candidates'/args.name
    if out.exists():raise RuntimeError('candidate already exists; choose a new version')
    out.mkdir(parents=True)
    if args.model:
        model=ROOT/'.local/guest-root/eval/model.bin';model.parent.mkdir(exist_ok=True)
        shutil.copyfile(args.model,model)
    shutil.copy2(ROOT/'.local/guest-root/shogi',out/'shogi')
    shutil.copyfile(build_path,out/'build.json')
    if args.model:shutil.copyfile(args.model,out/'model.bin')
    subprocess.run(['bash','scripts/build-guest-probe.sh','--engine',str(out/'root.ext2')],cwd=ROOT,check=True)
    report={'id':args.name,'complete':True,'guest_diagnostics':True,'search_diagnostics':True,'engine_sha256':sha(out/'shogi'),'image_sha256':sha(out/'root.ext2'),
            **identity,'build_key':build['build_key'],'build_manifest_sha256':sha(out/'build.json'),
            'feature_difference':args.feature_difference,
            'engine_options':{'EvalFile':'/eval/model.bin'} if args.model else {},
            'command':[str(ROOT/'run-shogi-1995.sh'),'--image',str(out/'root.ext2')]}
    if args.model:
        report.update(model_sha256=sha(out/'model.bin'),model_bytes=(out/'model.bin').stat().st_size,
                      model_origin=str(args.model.resolve()))
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
