#!/usr/bin/env python3
"""Compare complete, position-aligned runs with the same measurement conditions."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from shogi1995.statistics import paired

def main():
    p=argparse.ArgumentParser();p.add_argument('baseline',type=Path);p.add_argument('candidate',type=Path)
    p.add_argument('--output',required=True,type=Path);args=p.parse_args()
    a=json.loads(args.baseline.read_text());b=json.loads(args.candidate.read_text())
    if not (a['complete'] and b['complete']):raise ValueError('incomplete measurement')
    for key in ('dataset_sha256','sample_ids','mode','milliseconds','nodes','options'):
        if a[key]!=b[key]:raise ValueError('different measurement condition: '+key)
    result=paired(a['details'],b['details'])
    result.update(baseline=str(args.baseline),candidate=str(args.candidate),
                  baseline_accuracy=a['accuracy'],candidate_accuracy=b['accuracy'],
                  candidate_operational_pass=b['errors']==b['illegal_moves']==b['time_overruns']==0)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
