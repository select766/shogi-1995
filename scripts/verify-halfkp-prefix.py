#!/usr/bin/env python3
"""Compare all safely checkpointed rows of a partial sequential encode."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--reference',required=True,type=Path)
    p.add_argument('--candidate',required=True,type=Path);p.add_argument('--output',required=True,type=Path);args=p.parse_args()
    a=json.loads((args.reference/'manifest.json').read_text());b=json.loads((args.candidate/'manifest.json').read_text())
    if not b['complete']:raise ValueError('candidate encoding incomplete')
    for key in ['source_qsearch_output_sha256','validation_manifest_sha256','exclusions_sha256','feature_code_sha256','inputs','active','stride']:
        if a[key]!=b[key]:raise ValueError('different encoding input or layout: '+key)
    n=a['records']
    if not 0<n<=b['records']:raise ValueError('invalid reference prefix length')
    hashes={}
    for name,size in [('features.i4',a['active']*2*4),('targets.f4',4),('source-indices.u4',4)]:
        remaining=n*size;h=hashlib.sha256()
        with (args.reference/name).open('rb') as left,(args.candidate/name).open('rb') as right:
            while remaining:
                count=min(1024*1024,remaining);x=left.read(count);y=right.read(count)
                if len(x)!=count or x!=y:raise ValueError('prefix differs: '+name)
                h.update(x);remaining-=count
        hashes[name]=h.hexdigest()
    report={'passed':True,'verified_at_utc':datetime.now(timezone.utc).isoformat(),'accepted_rows_compared':n,
            'reference_complete':a['complete'],'candidate_complete':True,'prefix_hashes':hashes,
            'reference':str(args.reference.resolve()),'candidate':str(args.candidate.resolve()),
            'source_qsearch_output_sha256':a['source_qsearch_output_sha256']}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)


if __name__=='__main__':main()
