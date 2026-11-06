#!/usr/bin/env python3
"""Run the ordinary, unpaired tanuki qsearch + seeded shuffle on a fresh input."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from shogi1995.usi import Engine


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        while chunk:=f.read(1024*1024):h.update(chunk)
    return h.hexdigest()


def main():
    def interrupted(signum,frame):raise SystemExit(128+signum)
    signal.signal(signal.SIGTERM,interrupted)
    p=argparse.ArgumentParser();p.add_argument('--input',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path);p.add_argument('--threads',type=int,default=8)
    p.add_argument('--seed',type=int,default=20261106)
    p.add_argument('--engine',type=Path,default=ROOT/'.local/qsearch-tanuki/source/YaneuraOu-by-gcc')
    p.add_argument('--teacher',type=Path,default=ROOT/'.local/qsearch-tanuki/runtime/eval/nn.bin')
    args=p.parse_args()
    if args.output.exists():raise ValueError('output exists; preserve started preprocessing')
    if args.threads<1 or not 0<args.seed<2**31:p.error('positive threads and seed < 2**31 required')
    source=args.input.resolve();engine=args.engine.resolve();teacher=args.teacher.resolve()
    if source.stat().st_size%40:raise ValueError('input must contain 40-byte PSV records')
    out=args.output.resolve();out.mkdir(parents=True)
    inputs=out/'input';inputs.mkdir();(inputs/'original.bin').symlink_to(source)
    shuffled=out/'shuffled';shuffled.mkdir()
    # KifuWriter opens lazily, but the concatenation phase expects all buckets.
    for bucket in range(256):(shuffled/f'shuffled.{bucket:03d}.bin').touch()
    options={'Threads':args.threads,'USI_Hash':16,'EvalDir':str(teacher.parent),
             'KifuDir':str(inputs),'ShuffledKifuDir':str(shuffled),'ApplyQSearch':True,
             'PairedShuffle':False,'ShuffleSeed':args.seed,'MaxOutputSamples':0}
    report={'complete':False,'started_at_utc':datetime.now(timezone.utc).isoformat(),
            'input':str(source),'input_sha256':digest(source),'input_records':source.stat().st_size//40,
            'engine':str(engine),'engine_sha256':digest(engine),'teacher':str(teacher),'teacher_sha256':digest(teacher),
            'teacher_release':'https://github.com/nodchip/tanuki-/releases/tag/tanuki-.halfkp_256x2-32-32.2023-05-08',
            'teacher_fv_scale':20,'tanuki_source_commit':'cc38e5e284f44b038e9019d5bb19a0a7484bc9f1',
            'local_patches':['FV_SCALE=20 for the published teacher','bound each stdio buffer to 1 MiB'],
            'qsearch_semantics':'replace position by qsearch PV leaf; retain original teacher score and result with leaf-side sign; move=MOVE_NONE',
            'options':options,'script_sha256':digest(Path(__file__)),
            'measurement_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()}
    manifest=out/'manifest.json'
    def save():
        temp=manifest.with_suffix('.partial');temp.write_text(json.dumps(report,indent=2)+'\n');temp.replace(manifest)
    save();started=time.monotonic()
    try:
        with Engine([str(engine)],engine.parent,out/'logs',options) as client:
            report['engine_name']=client.name
            client.send('shuffle_kifu');client.send('isready')
            client.until('readyok',24*3600)
        result=shuffled/'shuffled.bin'
        if result.stat().st_size!=source.stat().st_size:raise ValueError('qsearch/shuffle changed record count')
        report.update(complete=True,output=str(result),output_sha256=digest(result),output_records=result.stat().st_size//40)
    finally:
        report['finished_at_utc']=datetime.now(timezone.utc).isoformat();report['elapsed_seconds']=time.monotonic()-started;save()
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':main()
