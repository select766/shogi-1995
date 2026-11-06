#!/usr/bin/env python3
"""Check frozen guest/native search equality before interpreting host node diagnostics."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from shogi1995.sessions import frozen_session,digest,COMMON
from shogi1995.usi import Engine


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True,type=Path)
    p.add_argument('--reference',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--count',type=int,default=8);p.add_argument('--automatic-model',action='store_true')
    p.add_argument('--expected-output-bits',type=int,choices=[32,64]);args=p.parse_args()
    if args.output.exists():raise ValueError('output exists')
    ref=json.loads(args.reference.read_text());manifest=json.loads(args.manifest.read_text())
    assert ref['complete'] and ref['mode']=='fixed_nodes' and ref['engine_sha256']==manifest['engine_sha256']
    assert ref.get('model_sha256',ref.get('guest_model_sha256'))==manifest.get('model_sha256')
    if not 0<args.count<=len(ref['details']):raise ValueError('invalid count')
    rows=[];counters=None;started=datetime.now(timezone.utc).isoformat()
    if args.automatic_model:
        image=Path(manifest['command'][manifest['command'].index('--image')+1])
        assert digest(image)==manifest['image_sha256'] and manifest.get('configured_guest_options')
        client=Engine(manifest['command'],ROOT,args.output.with_suffix('.logs'),COMMON)
    else:
        client=frozen_session(args.manifest.resolve(),ROOT/'.local/parity-runs'/args.output.stem,args.output.with_suffix('.logs'))
    with client as engine:
        if args.automatic_model:
            engine.send('getoption EvalFile');_,lines=engine.until('Options[EvalFile]',10)
            assert lines[-1].split('=',1)[1].strip()==manifest['configured_guest_options']['EvalFile']
        for expected in ref['details'][:args.count]:
            engine.reset();actual=engine.search(expected['sfen'],nodes=ref['nodes'],diagnostics=manifest.get('search_diagnostics',False))
            assert actual['actual']==expected['actual'],(expected['id'],expected['actual'],actual)
            assert actual.get('final_nodes',actual['nodes'])==expected.get('final_nodes',expected['nodes']),(expected,actual)
            if 'completed_depth' in actual and 'completed_depth' in expected:
                assert actual['completed_depth']==expected['completed_depth'],(expected,actual)
            rows.append({'id':expected['id'],'bestmove':actual['actual'],'nodes':actual.get('final_nodes',actual['nodes']),
                         'completed_depth':actual.get('completed_depth')})
        if args.expected_output_bits is not None:
            engine.send('shogi1995evalstats');_,lines=engine.until('info string shogi1995 accumulators ',10)
            counters={k:int(v) for k,v in (item.split('=') for item in lines[-1].split()[4:])}
            assert counters.get('output_bits')==args.expected_output_bits,counters
    result={'passed':True,'started_at_utc':started,'finished_at_utc':datetime.now(timezone.utc).isoformat(),
            'measurement_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'positions':len(rows),'engine_sha256':manifest['engine_sha256'],'model_sha256':manifest.get('model_sha256'),
            'automatic_model_selection':args.automatic_model,
            'guest_eval_counters':counters,
            'reference_sha256':digest(args.reference),'rows':rows,
            'scope':'search parity; host timing/NPS are not Pentium performance measurements'}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
