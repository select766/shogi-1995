#!/usr/bin/env python3
"""Check checkpoint-to-file export and full held-out integer quantization error."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import torch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from shogi1995.halfkp_features import INPUTS,ACTIVE
from shogi1995.halfkp_linear import load


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        while data:=f.read(1024*1024):h.update(data)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--model',required=True,type=Path)
    p.add_argument('--validation',required=True,type=Path);p.add_argument('--output',required=True,type=Path);args=p.parse_args()
    if args.output.exists():raise ValueError('output exists')
    report=json.loads((args.model/'manifest.json').read_text());source=json.loads((args.validation/'manifest.json').read_text())
    if not report['complete'] or not source['complete']:raise ValueError('complete artifacts required')
    if report['identity']['data_manifests']['validation']!=digest(args.validation/'manifest.json'):
        raise ValueError('validation is not the training run held-out set')
    model=args.model/'model.bin'
    if digest(model)!=report['model_sha256']:raise ValueError('model hash differs')
    quantized=load(model);state=torch.load(args.model/'best.pt',map_location='cpu',weights_only=True)
    weights=state['embedding.weight'][:,0]
    assert tuple(weights.shape)==(INPUTS,)
    expected=np.rint((weights.numpy()*600).astype(np.float64)*256).astype(np.int64)
    if not np.array_equal(expected,quantized):raise ValueError('integer file does not export the selected checkpoint')
    for name,key in [('features.i4','features_sha256'),('targets.f4','targets_sha256')]:
        if digest(args.validation/name)!=source[key]:raise ValueError('validation data hash differs')
    if not torch.cuda.is_available():raise RuntimeError('CUDA required; no fallback')
    torch.set_num_threads(4);device=torch.device('cuda');n=source['records']
    x=np.memmap(args.validation/'features.i4',dtype='<i4',mode='r',shape=(n,2,ACTIVE))
    y=np.memmap(args.validation/'targets.f4',dtype='<f4',mode='r',shape=(n,))
    table=weights.to(device);qtable=torch.from_numpy(quantized).to(device)
    errors=[];float_loss=integer_loss=0.;clipped=0
    with torch.no_grad():
        for start in range(0,n,16384):
            features=torch.from_numpy(np.array(x[start:start+16384],copy=True)).to(device)
            target=torch.from_numpy(np.array(y[start:start+16384],copy=True)).to(device)
            f=table[features].sum(dim=2);logits=f[:,0]-f[:,1]
            q=qtable[features].sum(dim=2);raw=q[:,0]-q[:,1]
            integer=torch.where(raw>=0,(raw+128)//256,-((-raw+128)//256)).clamp(-12000,12000).float()
            teacher=torch.sigmoid(target/600)
            float_loss+=torch.nn.functional.binary_cross_entropy_with_logits(logits,teacher,reduction='sum').item()
            integer_loss+=torch.nn.functional.binary_cross_entropy_with_logits(integer/600,teacher,reduction='sum').item()
            errors.append((integer-logits*600).cpu().numpy());clipped+=int((logits.abs()*600>12000).sum().item())
    errors=np.concatenate(errors).astype(np.float64)
    result={'passed':True,'positions':n,'checkpoint_export_exact_all_weights':True,
            'float_validation_loss':float_loss/n,'integer_validation_loss':integer_loss/n,
            'score_quantization_rmse':float(np.sqrt(np.mean(errors**2))),
            'score_abs_error_p99':float(np.quantile(np.abs(errors),.99)),'score_abs_error_max':float(np.max(np.abs(errors))),
            'floating_scores_outside_inference_clamp':clipped,'weight_min_cp':float(weights.min()*600),'weight_max_cp':float(weights.max()*600),
            'model_sha256':digest(model),'checkpoint_sha256':digest(args.model/'best.pt'),'validation_manifest_sha256':digest(args.validation/'manifest.json'),
            'validator_sha256':digest(Path(__file__)),'scope':'quantization diagnostic; not move agreement or strength'}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)


if __name__=='__main__':main()
