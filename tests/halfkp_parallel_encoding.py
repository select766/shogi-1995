#!/usr/bin/env python3
"""Require byte-identical ordered features and benchmark host preprocessing only."""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import cshogi
import numpy as np

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser();p.add_argument('--work',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path);args=p.parse_args()
    if args.work.exists():raise ValueError('preserve previous verification')
    args.work.mkdir(parents=True)
    base=Path('/media/select766/HDCZ-UT/s7ubuntu/dev/shogi-1995/training')
    validation=base/'halfkp-features-v1/validation';exclusions=Path('/media/select766/HDCZ-UT/s7ubuntu/dev/shogi-1995/evaluation/floodgate-hcpe-1995-v1/excluded-sfen.txt')
    rows=np.fromfile(base/'halfkp-qsearch-input-v1/train.bin',dtype=cshogi.PackedSfenValue,count=131072)
    assert len(rows)==131072
    raw=args.work/'input.bin';rows.tofile(raw)
    def call(script,*parts):subprocess.run([sys.executable,str(ROOT/script),*map(str,parts)],cwd=ROOT,check=True)
    q=args.work/'qsearch';call('scripts/qsearch-shuffle.py','--input',raw,'--output',q,'--threads',4)
    common=['--qsearch-manifest',q/'manifest.json','--validation',validation]
    serial=args.work/'serial';parallel=args.work/'parallel'
    call('scripts/encode-halfkp-data.py',*common,'--split','train','--output',serial)
    call('scripts/encode-halfkp-parallel.py',*common,'--workers',4,'--chunk-records',16384,'--output',parallel)
    a=json.loads((serial/'manifest.json').read_text());b=json.loads((parallel/'manifest.json').read_text())
    for key in ['records','processed','rejections','features_sha256','targets_sha256','source_indices_sha256','position_keys_sha256']:
        assert a[key]==b[key],key
    spec=importlib.util.spec_from_file_location('halfkp_parallel',ROOT/'scripts/encode-halfkp-parallel.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    prod=json.loads((base/'halfkp-qsearch-v1/raw-train/manifest.json').read_text())
    module.initialize(prod['output'],str(exclusions),str(validation/'position-keys.txt'))
    end,x,y,indices,count,counts=module.chunk((0,65536))
    old=base/'halfkp-features-v1/train'
    for name,expected in [('features.i4',x),('targets.f4',y),('source-indices.u4',indices)]:
        with (old/name).open('rb') as f:assert f.read(len(expected))==expected,name
    report={'passed':True,'fixture_input_records':len(rows),'accepted_records':a['records'],
            'features_targets_indices_and_keys_identical':True,'rejection_counts_identical':True,
            'production_prefix_raw_records':end,'production_prefix_accepted_records':count,
            'production_prefix_matches_existing_sequential_run':True,'workers':4,
            'serial_seconds':a['elapsed_seconds'],'parallel_seconds':b['elapsed_seconds'],
            'speed_ratio':a['elapsed_seconds']/b['elapsed_seconds'],
            'scope':'host preprocessing throughput only; no Pentium strength or speed claim'}
    args.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)


if __name__=='__main__':main()
