#!/usr/bin/env python3
"""GPU/resume/export and scalar NN03 checks; run after real-time measurement."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import cshogi
import torch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from shogi1995.halfkp_network import HalfKPNetwork,export
from shogi1995.halfkp_features import INPUTS,STRIDE
from shogi1995 import tiny_quant,halfkp_linear
from shogi1995.sessions import COMMON
from shogi1995.usi import Engine


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def equal(a,b):
    if isinstance(a,torch.Tensor):assert torch.equal(a,b)
    elif isinstance(a,dict):
        assert a.keys()==b.keys()
        for key in a:equal(a[key],b[key])
    elif isinstance(a,(list,tuple)):
        assert len(a)==len(b)
        for x,y in zip(a,b):equal(x,y)
    else:assert a==b,(a,b)


def main():
    p=argparse.ArgumentParser();p.add_argument('--work',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path);args=p.parse_args()
    if args.work.exists() or args.output.exists():raise ValueError('preserve previous test attempt')
    args.work.mkdir(parents=True)
    fixture=ROOT/'.local/tests/halfkp-training-smoke-v2/encoded'
    data=Path('/media/select766/HDCZ-UT/s7ubuntu/dev/shogi-1995/training/halfkp-qsearch-v1/raw-validation/shuffled/shuffled.bin')
    quick=Path('/media/select766/HDCZ-UT/s7ubuntu/dev/shogi-1995/evaluation/floodgate-hcpe-1995-v1/quick.jsonl')
    def call(script,*parts):
        result=subprocess.run([sys.executable,str(ROOT/script),*map(str,parts)],cwd=ROOT,text=True,capture_output=True)
        if result.returncode:raise RuntimeError(result.stdout[-4000:]+'\n'+result.stderr[-4000:])
        return result.stdout
    common=['--data',fixture,'--batch',128,'--chunk-records',300,'--min-epochs',1,'--min-examples',0,'--width',8,'--hidden',0]
    full=args.work/'continuous';resumed=args.work/'resumed'
    call('scripts/train-halfkp-nnue.py',*common,'--output',full,'--max-epochs',2)
    call('scripts/train-halfkp-nnue.py',*common,'--output',resumed,'--max-epochs',1)
    call('scripts/train-halfkp-nnue.py',*common,'--output',resumed,'--max-epochs',2,'--resume')
    a=torch.load(full/'last.pt',map_location='cpu',weights_only=False)
    b=torch.load(resumed/'last.pt',map_location='cpu',weights_only=False)
    for key in ['model','optimizer','scheduler','cpu_rng','cuda_rng']:equal(a[key],b[key])
    for left,right in zip(a['history'],b['history']):
        for key in ['train_loss','validation_loss','learning_rate','next_learning_rate','chunk_order','examples_seen']:
            equal(left[key],right[key])
    assert (full/'model.bin').read_bytes()==(resumed/'model.bin').read_bytes()
    assert not json.loads((full/'manifest.json').read_text())['converged']
    qat=args.work/'qat'
    call('scripts/train-halfkp-nnue.py','--data',fixture,'--batch',128,'--chunk-records',300,
         '--min-epochs',1,'--min-examples',0,'--width',16,'--hidden',8,'--qat','--max-epochs',2,'--output',qat)
    models=[]
    for width,hidden in [(8,0),(16,0),(16,8)]:
        torch.manual_seed(20261106+width+hidden);model=HalfKPNetwork(width,hidden)
        with torch.no_grad():
            model.embedding.weight.normal_(0,.08);model.embedding.weight[INPUTS].zero_()
            model.embedding.weight[torch.arange(81)*STRIDE]=0
            model.bias.fill_(.3);model.out.weight.normal_(0,.3);model.out.bias.fill_(.04)
            if model.fc is not None:model.fc.weight.normal_(0,.2);model.fc.bias.fill_(.1)
        path=args.work/f'synthetic-w{width}-h{hidden}.bin';export(model,path);models.append(path)
    parities=[]
    for model in [*models,full/'model.bin',qat/'model.bin']:
        value=json.loads(call('tests/tiny_parity.py','--model',model,'--data',data,'--count',512))
        assert value['passed'];parities.append({'model_sha256':digest(model),**value})
    binary=ROOT/'.local/guest-root/shogi';model=models[0];options={**COMMON,'EvalFile':str(model.resolve())}
    records=[json.loads(line) for line in quick.read_text().splitlines() if line.strip()]
    reference={'complete':True,'mode':'fixed_nodes','nodes':10000,'options':COMMON,'capture_search_diagnostics':True,'details':[]}
    with Engine([str(binary)],ROOT,args.work/'reference.logs',options) as client:
        for row in records:
            client.reset();result=client.search(row['sfen'],nodes=10000,diagnostics=True)
            reference['details'].append({'id':row['id'],'sfen':row['sfen'],**result})
    ref=args.work/'reference.json';ref.write_text(json.dumps(reference,indent=2)+'\n')
    incremental=args.work/'incremental.json'
    call('tests/tiny_incremental.py','--model',model,'--reference',ref,'--output',incremental)
    board=cshogi.Board(records[0]['sfen']);values=[]
    with Engine([str(binary)],ROOT,args.work/'switch.logs',{**options,'EvalVerify':True}) as client:
        client.send('position sfen '+board.sfen())
        linear=ROOT/'.local/candidates/halfkp-linear-v2/model.bin'
        for path in [models[0],models[1],linear,models[0]]:
            client.send('setoption name EvalFile value '+str(path.resolve()))
            client.send('isready');client.until('readyok',60)
            # This engine resets its position on isready; restore it as a USI client does.
            client.send('position sfen '+board.sfen())
            client.send('shogi1995eval');_,lines=client.until('info string shogi1995 eval ',10)
            arithmetic=halfkp_linear if path==linear else tiny_quant
            expected=arithmetic.reference(board,arithmetic.load(path))
            actual=int(lines[-1].split()[-1]);assert actual==expected,(path,actual,expected)
            values.append(actual)
    assert len(set(values))>1 and values[0]==values[-1]
    result={'passed':True,'gpu_resume_parameters_optimizer_scheduler_rng_and_losses_identical':True,
            'best_export_byte_identical':True,'qat_training_operational':True,'root_parities':parities,
            'incremental':json.loads(incremental.read_text()),'model_switch_values_after_ready_and_position':values,
            'engine_sha256':digest(binary),'scope':'operational validation only; synthetic and short-trained models are not strength candidates'}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)


if __name__=='__main__':main()
