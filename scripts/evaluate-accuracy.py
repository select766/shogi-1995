#!/usr/bin/env python3
"""Measure a fixed JSONL set, preserving every expected position and all failures."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
import subprocess

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
import cshogi
from shogi1995.usi import Engine
from shogi1995.statistics import summary
from shogi1995.actions import classify
from shogi1995.provenance import environment_identity


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--no-history',action='store_true',help='Do not update shared measurement history')
    p.add_argument('--dataset',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--engine-command',required=True,help='JSON array of argv strings, never evaluated as a shell')
    p.add_argument('--engine-id',required=True);p.add_argument('--engine-sha256',required=True)
    p.add_argument('--engine-options',default='{}',help='Model-specific options, JSON object')
    p.add_argument('--milliseconds',type=int,default=2000);p.add_argument('--nodes',type=int)
    p.add_argument('--guest-diagnostics',action='store_true',help='Query project-specific in-guest memory statistics')
    p.add_argument('--search-diagnostics',action='store_true',help='Query project-specific final search counters after bestmove')
    p.add_argument('--engine-manifest',type=Path,help='Frozen artifact/source identity for the measurement history')
    p.add_argument('--feature-difference',default='',help='Main changes versus the baseline, for the measurement history')
    p.add_argument('--backend',choices=('86box','native','qemu'))
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
    if args.backend is None:
        args.backend='86box' if any(Path(token).name=='run-shogi-1995.sh' for token in command) else 'native'
        if '--backend' in command and command[command.index('--backend')+1]=='qemu':args.backend='qemu'
    artifact_hashes={}
    if args.backend=='native' and len(command)==1 and Path(command[0]).is_file():
        actual=hashlib.sha256(Path(command[0]).read_bytes()).hexdigest()
        if actual!=args.engine_sha256:raise ValueError('native binary SHA does not match declared engine')
        artifact_hashes['native_binary_sha256']=actual
        if model_options.get('EvalFile') not in (None,'<none>'):
            model=Path(model_options['EvalFile'])
            if not model.is_absolute():raise ValueError('native model path must be absolute for reliable provenance')
            artifact_hashes['native_model_sha256']=hashlib.sha256(model.read_bytes()).hexdigest()
    if '--image' in command:
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
            'started_at_utc':datetime.now(timezone.utc).isoformat(),
            'measurement_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'measurement_worktree_dirty':bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()),
            'measurement_sources':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
                                   ('scripts/evaluate-accuracy.py','src/shogi1995/usi.py','src/shogi1995/actions.py','src/bridge/main.py')},
            'backend':args.backend,'feature_difference':args.feature_difference,
            'environment':environment_identity(args.backend),
            'dataset_sha256':hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
            'dataset':str(args.dataset.resolve()),'sample_ids':[r['id'] for r in records],
            'offset':args.offset,
            'capture_search_diagnostics':args.search_diagnostics,
            'mode':'fixed_nodes' if args.nodes is not None else 'fixed_byoyomi',
            'milliseconds':args.milliseconds,'nodes':args.nodes,'options':options,
            'engine_command':json.loads(args.engine_command),'complete':False,'details':[]}
    report.update(artifact_hashes)
    if args.engine_manifest:
        identity=json.loads(args.engine_manifest.read_text())
        if identity['engine_sha256']!=args.engine_sha256:raise ValueError('engine manifest SHA mismatch')
        for key in ('model_sha256','image_sha256','source_tree_sha256','source_commit','source_worktree_dirty','source_commit_binding'):
            if key in identity:report[key]=identity[key]
        for key,actual in (('model_sha256','guest_model_sha256'),('image_sha256','guest_image_sha256')):
            if key in identity and actual in report and identity[key]!=report[actual]:raise ValueError('artifact manifest mismatch: '+key)
        if 'native_model_sha256' in report and identity.get('model_sha256')!=report['native_model_sha256']:
            raise ValueError('native model differs from frozen manifest')
        if not report['feature_difference']:report['feature_difference']=identity.get('feature_difference','')
    if not report['feature_difference']:report['feature_difference']='変更点未記入（要追記）'
    def save():
        report.update(summary(report['details'],len(records)))
        tmp=args.output.with_suffix('.partial');tmp.write_text(json.dumps(report,indent=2)+'\n');tmp.replace(args.output)
    save();started=time.monotonic();board=cshogi.Board()
    def memory(engine):
        engine.send('shogi1995stats')
        _,lines=engine.until('info string shogi1995 memory ',10)
        return {key:int(value) for key,value in (item.split('=') for item in lines[-1].split()[4:])}
    try:
        with Engine(report['engine_command'],ROOT,str(args.output)+'.logs',{**options,**model_options}) as engine:
            report['engine_name']=engine.name
            report['advertised_options']=engine.options
            if args.guest_diagnostics:
                report['guest_memory']=memory(engine)
            for i,r in enumerate(records):
                row={'id':r['id'],'sfen':r['sfen'],'expected':r['bestmove'],'match':False}
                try:
                    engine.reset()
                    row.update(engine.search(r['sfen'],args.milliseconds,args.nodes,args.search_diagnostics))
                    board.set_sfen(r['sfen'])
                    row.update(classify(board,row['actual']))
                    row['time_overrun']=args.nodes is None and row['host_ms']>args.milliseconds+200
                    row['match']=row['legal'] and not row['time_overrun'] and row['actual']==row['expected']
                except (TimeoutError,RuntimeError,OSError) as error:
                    row['error']=str(error);report['details'].append(row);save();raise
                report['details'].append(row)
                report['elapsed_seconds']=time.monotonic()-started;save()
                print(f'{i+1}/{len(records)} matches={report["matches"]} accuracy={report["accuracy"]:.4f}',flush=True)
            if args.guest_diagnostics:report['guest_memory_end']=memory(engine)
            report['complete']=True
    finally:
        report['elapsed_seconds']=time.monotonic()-started
        report['finished_at_utc']=datetime.now(timezone.utc).isoformat();save()
        if report['complete'] and not args.no_history:
            subprocess.run([sys.executable,str(ROOT/'scripts/update-measurements.py'),'--result',str(args.output.resolve())],cwd=ROOT,check=True)
    print(json.dumps({k:v for k,v in report.items() if k not in ('details','sample_ids')},indent=2))


if __name__=='__main__':main()
