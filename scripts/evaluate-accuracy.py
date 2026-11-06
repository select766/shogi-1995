#!/usr/bin/env python3
"""Measure a fixed JSONL set, preserving every expected position and all failures."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
import cshogi
from shogi1995.usi import Engine
from shogi1995.statistics import summary


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--dataset',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--engine-command',required=True,help='JSON array of argv strings, never evaluated as a shell')
    p.add_argument('--engine-id',required=True);p.add_argument('--engine-sha256',required=True)
    p.add_argument('--engine-options',default='{}',help='Model-specific options, JSON object')
    p.add_argument('--milliseconds',type=int,default=2000);p.add_argument('--nodes',type=int)
    p.add_argument('--guest-diagnostics',action='store_true',help='Query project-specific in-guest memory statistics')
    p.add_argument('--limit',type=int);p.add_argument('--offset',type=int,default=0);args=p.parse_args()
    if args.offset<0:p.error('offset must be nonnegative')
    if args.milliseconds<=0 or (args.nodes is not None and args.nodes<=0) or (args.limit is not None and args.limit<=0):
        p.error('time, nodes and limit must be positive')
    records=[json.loads(s) for s in args.dataset.read_text().splitlines() if s.strip()]
    records=records[args.offset:]
    if args.limit is not None:records=records[:args.limit]
    if not records:raise ValueError('empty evaluation dataset')
    if args.output.exists():raise RuntimeError('output exists; choose a new run, never overwrite results')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    options={'Threads':1,'USI_Hash':2,'USI_OwnBook':False,'USI_Ponder':False,'MultiPV':1,
             'MaxMovesToDraw':512,'EnteringKingRule':'CSARule27','NetworkDelay':0,'NetworkDelay2':0}
    model_options=json.loads(args.engine_options)
    if set(model_options)&set(options):raise ValueError('model options may not override common measurement settings')
    command=json.loads(args.engine_command)
    artifact_hashes={}
    if '--image' in command:
        import subprocess
        image=Path(command[command.index('--image')+1]).resolve()
        binary=subprocess.check_output(['debugfs','-R','cat /shogi',str(image)],stderr=subprocess.DEVNULL)
        if hashlib.sha256(binary).hexdigest()!=args.engine_sha256:raise ValueError('guest binary SHA does not match declared engine')
        h=hashlib.sha256()
        with image.open('rb') as f:
            while block:=f.read(1024*1024):h.update(block)
        artifact_hashes['guest_image_sha256']=h.hexdigest()
        if model_options.get('EvalFile') not in (None,'<none>'):
            model=subprocess.check_output(['debugfs','-R','cat '+model_options['EvalFile'],str(image)],stderr=subprocess.DEVNULL)
            if not model:raise ValueError('empty or missing guest model')
            artifact_hashes['guest_model_sha256']=hashlib.sha256(model).hexdigest()
    report={'engine_id':args.engine_id,'engine_sha256':args.engine_sha256,'model_options':model_options,
            'dataset_sha256':hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
            'dataset':str(args.dataset.resolve()),'sample_ids':[r['id'] for r in records],
            'offset':args.offset,
            'mode':'fixed_nodes' if args.nodes is not None else 'fixed_byoyomi',
            'milliseconds':args.milliseconds,'nodes':args.nodes,'options':options,
            'engine_command':json.loads(args.engine_command),'complete':False,'details':[]}
    report.update(artifact_hashes)
    def save():
        report.update(summary(report['details'],len(records)))
        tmp=args.output.with_suffix('.partial');tmp.write_text(json.dumps(report,indent=2)+'\n');tmp.replace(args.output)
    save();started=time.monotonic();board=cshogi.Board()
    try:
        with Engine(report['engine_command'],ROOT,str(args.output)+'.logs',{**options,**model_options}) as engine:
            report['engine_name']=engine.name
            report['advertised_options']=engine.options
            if args.guest_diagnostics:
                engine.send('shogi1995stats')
                _,lines=engine.until('info string shogi1995 memory ',10)
                report['guest_memory']={key:int(value) for key,value in (item.split('=') for item in lines[-1].split()[4:])}
            for i,r in enumerate(records):
                row={'id':r['id'],'sfen':r['sfen'],'expected':r['bestmove'],'match':False}
                try:
                    engine.reset()
                    row.update(engine.search(r['sfen'],args.milliseconds,args.nodes))
                    board.set_sfen(r['sfen'])
                    try:move=board.move_from_usi(row['actual']);row['legal']=bool(board.is_legal(move))
                    except (ValueError,RuntimeError):row['legal']=False
                    row['time_overrun']=args.nodes is None and row['host_ms']>args.milliseconds+200
                    row['match']=row['legal'] and not row['time_overrun'] and row['actual']==row['expected']
                except (TimeoutError,RuntimeError,OSError) as error:
                    row['error']=str(error);report['details'].append(row);save();raise
                report['details'].append(row)
                report['elapsed_seconds']=time.monotonic()-started;save()
                print(f'{i+1}/{len(records)} matches={report["matches"]} accuracy={report["accuracy"]:.4f}',flush=True)
            report['complete']=True
    finally:
        report['elapsed_seconds']=time.monotonic()-started;save()
    print(json.dumps({k:v for k,v in report.items() if k not in ('details','sample_ids')},indent=2))


if __name__=='__main__':main()
