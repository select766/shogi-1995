#!/usr/bin/env python3
"""Compare complete, position-aligned runs with the same measurement conditions."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from shogi1995.statistics import paired
from shogi1995.comparison import validate_conditions, stratified
from shogi1995.performance import compare_performance

def main():
    p=argparse.ArgumentParser();p.add_argument('baseline',type=Path);p.add_argument('candidate',type=Path)
    p.add_argument('--output',required=True,type=Path);args=p.parse_args()
    a=json.loads(args.baseline.read_text());b=json.loads(args.candidate.read_text())
    validate_conditions(a,b)
    result=paired(a['details'],b['details'])
    result.update(baseline=str(args.baseline),candidate=str(args.candidate),
                  baseline_accuracy=a['accuracy'],candidate_accuracy=b['accuracy'],
                  candidate_operational_pass=b['errors']==b['illegal_moves']==b['time_overruns']==0)
    result['baseline_operational_pass']=a['errors']==a['illegal_moves']==a['time_overruns']==0
    result['comparison_operational_pass']=result['baseline_operational_pass'] and result['candidate_operational_pass']
    result['performance']=compare_performance(a['details'],b['details'])
    result['comparison_sources']={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
                                  ('scripts/compare-accuracy.py','src/shogi1995/comparison.py','src/shogi1995/statistics.py','src/shogi1995/performance.py')}
    dataset=Path(a['dataset'])
    if dataset.is_file():
        contents=dataset.read_bytes()
        if hashlib.sha256(contents).hexdigest()!=a['dataset_sha256']:
            raise ValueError('stratification dataset hash differs')
        records=[json.loads(line) for line in contents.splitlines() if line.strip()]
        result['diagnostics']=stratified(a['details'],b['details'],records)
    else:
        result['diagnostics']={'unavailable':'original dataset file is not accessible'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
