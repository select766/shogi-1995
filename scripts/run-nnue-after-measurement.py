#!/usr/bin/env python3
"""Owned deferred work: wait for one live measurement, then build/test/train."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from shogi1995.provenance import source_tree_hash


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def process_identity(pid):
    try:
        fields=Path(f'/proc/{pid}/stat').read_text().split(') ',1)[1].split()
        return fields[0],fields[19]
    except FileNotFoundError:return None,None


def main():
    p=argparse.ArgumentParser();p.add_argument('--plan',required=True,type=Path)
    p.add_argument('--state',required=True,type=Path);args=p.parse_args()
    if args.state.exists():raise ValueError('state exists; inspect previous attempt')
    plan=json.loads(args.plan.read_text());pair=ROOT/plan['measurement_output']
    state={'status':'waiting_for_measurement','started_at_utc':datetime.now(timezone.utc).isoformat(),
           'plan_sha256':digest(args.plan),'pid':os.getpid()};child=None
    args.state.parent.mkdir(parents=True,exist_ok=True)
    def save():
        temp=args.state.with_suffix('.partial');temp.write_text(json.dumps(state,indent=2)+'\n');temp.replace(args.state)
    def interrupted(signum,frame):raise SystemExit(128+signum)
    signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGINT,interrupted)
    save()
    try:
        while True:
            completed=pair/'comparison.json'
            if completed.exists():
                try:
                    comparison=json.loads(completed.read_text())
                    reports=[json.loads((pair/(key+'.json')).read_text()) for key in ['baseline','candidate']]
                except json.JSONDecodeError:
                    time.sleep(1);continue
                if not all(r['complete'] and r['total']==1024 and r['measured']==1024 for r in reports):
                    raise ValueError('final measurement is not complete')
                if digest(pair/'identity.json')!=plan['measurement_identity_sha256']:
                    raise ValueError('measurement identity changed')
                for report in reports:
                    if (report['dataset_sha256']!=plan['dataset_sha256'] or report['sample_ids']!=plan['sample_ids']
                            or report['backend']!='86box' or report['mode']!='fixed_byoyomi'
                            or report['milliseconds']!=2000 or report['nodes'] is not None):
                        raise ValueError('measurement conditions differ from the planned completed run')
                if not comparison.get('comparison_operational_pass'):raise ValueError('measurement requires operational investigation')
                state['measurement_comparison_sha256']=digest(completed);break
            status,start=process_identity(plan['producer_pid'])
            if status in (None,'Z') or start!=plan['producer_start_time']:
                raise RuntimeError('measurement producer stopped without a complete comparison; do not restart it automatically')
            time.sleep(2)
        if source_tree_hash()!=plan['source_tree_sha256']:raise ValueError('planned engine source changed')
        for name,expected in plan['code_sha256'].items():
            if digest(ROOT/name)!=expected:raise ValueError('planned code changed: '+name)
        for name,expected in plan.get('input_manifest_sha256',{}).items():
            if digest(Path(name))!=expected:raise ValueError('planned input manifest changed: '+name)
        state['status']='executing';save()
        for index,step in enumerate(plan['steps'],1):
            state.update(step=index,description=step['description'],log=step['log']);save()
            with Path(step['log']).open('w') as log:
                child=subprocess.Popen(step['argv'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                state['child_pid']=child.pid;save();code=child.wait();child=None;state['child_pid']=None
            if code:raise RuntimeError(f"step {index} exited {code}: {step['description']}")
        state['status']='complete'
    except BaseException as error:
        state['status']='stopped';state['error']=str(error)
        if child is not None and child.poll() is None:
            try:os.killpg(child.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            try:child.wait(10)
            except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
        raise
    finally:
        state['updated_at_utc']=datetime.now(timezone.utc).isoformat();save()


if __name__=='__main__':main()
