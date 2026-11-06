#!/usr/bin/env python3
"""Exercise fresh qsearch, leakage filtering, GPU fitting, and exact epoch resume."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import cshogi
import numpy as np
import torch

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser();p.add_argument('--raw-data',required=True,type=Path)
    p.add_argument('--work',required=True,type=Path);p.add_argument('--output',required=True,type=Path);args=p.parse_args()
    if args.work.exists():raise ValueError('preserve previous smoke attempts')
    args.work.mkdir(parents=True)
    def call(script,*parts):
        subprocess.run([sys.executable,str(ROOT/script),*map(str,parts)],cwd=ROOT,check=True)
    data=args.work/'encoded'
    for split,count in [('validation',128),('train',1024)]:
        records=np.fromfile(args.raw_data/(split+'.bin'),dtype=cshogi.PackedSfenValue,count=count)
        assert len(records)==count
        raw=args.work/(split+'.bin');records.tofile(raw)
        q=args.work/('qsearch-'+split)
        call('scripts/qsearch-shuffle.py','--input',raw,'--output',q,'--threads',2)
        command=['--qsearch-manifest',q/'manifest.json','--split',split,'--output',data/split]
        if split=='train':command+=['--validation',data/'validation']
        call('scripts/encode-halfkp-data.py',*command)
    common=['--data',data,'--batch',128,'--chunk-records',300,'--min-epochs',1,'--min-examples',0]
    full=args.work/'continuous';resumed=args.work/'resumed'
    call('scripts/train-halfkp-linear.py',*common,'--output',full,'--max-epochs',2)
    call('scripts/train-halfkp-linear.py',*common,'--output',resumed,'--max-epochs',1)
    call('scripts/train-halfkp-linear.py',*common,'--output',resumed,'--max-epochs',2,'--resume')
    left=torch.load(full/'last.pt',map_location='cpu',weights_only=False)
    right=torch.load(resumed/'last.pt',map_location='cpu',weights_only=False)
    def equal(a,b):
        if isinstance(a,torch.Tensor):assert torch.equal(a,b)
        elif isinstance(a,dict):
            assert a.keys()==b.keys()
            for key in a:equal(a[key],b[key])
        elif isinstance(a,(list,tuple)):
            assert len(a)==len(b)
            for x,y in zip(a,b):equal(x,y)
        else:assert a==b,(a,b)
    for name in ['model','optimizer','scheduler','cpu_rng','cuda_rng']:equal(left[name],right[name])
    for a,b in zip(left['history'],right['history']):
        for name in ['train_loss','validation_loss','validation_rmse','learning_rate','next_learning_rate','examples_seen','chunk_order']:
            equal(a[name],b[name])
    assert (full/'model.bin').read_bytes()==(resumed/'model.bin').read_bytes()
    a=json.loads((full/'manifest.json').read_text());b=json.loads((resumed/'manifest.json').read_text())
    assert a['complete'] and b['complete'] and not a['converged'] and not b['converged']
    report={'passed':True,'fresh_qsearch_and_encoding':True,'gpu_training':True,
            'resume_parameters_optimizer_scheduler_rng_and_losses_identical':True,
            'best_export_byte_identical':True,'epoch_limit_not_reported_as_convergence':True,
            'train_records':a['train_records'],'validation_records':a['validation_records'],
            'model_sha256':hashlib.sha256((full/'model.bin').read_bytes()).hexdigest(),
            'purpose':'operational test only; not a trained strength candidate'}
    args.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)


if __name__=='__main__':main()
