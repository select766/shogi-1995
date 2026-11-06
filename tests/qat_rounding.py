#!/usr/bin/env python3
"""Check STE rounding and its score agreement with independent exported arithmetic."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import cshogi
import numpy as np
import torch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from shogi1995.tiny_quant import load, reference
from shogi1995.tiny_features import encode, SYMMETRIC_INPUTS


def main():
    p=argparse.ArgumentParser();p.add_argument('--model',required=True,type=Path);p.add_argument('--checkpoint',required=True,type=Path)
    p.add_argument('--data',required=True,type=Path);args=p.parse_args()
    spec=importlib.util.spec_from_file_location('trainer',ROOT/'scripts/train-tiny.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    torch.set_num_threads(2)
    x=torch.tensor([-1.5,-.5,.5,1.5],requires_grad=True)
    torch.testing.assert_close(module.quantize(x,1),torch.tensor([-2.,0.,0.,2.]))
    out=module.quantize(x,1,'away');torch.testing.assert_close(out,torch.tensor([-2.,-1.,1.,2.]))
    out.sum().backward();torch.testing.assert_close(x.grad,torch.ones(4))
    weights=load(args.model);embedding,_,fc,_,_,_=weights
    model=module.Tiny(embedding.shape[1],len(fc),len(embedding),qat=True)
    model.load_state_dict(torch.load(args.checkpoint,map_location='cpu',weights_only=True))
    records=np.memmap(args.data,dtype=cshogi.PackedSfenValue,mode='r');board=cshogi.Board()
    features=[];materials=[];expected=[]
    for index in np.linspace(0,len(records)-1,1024,dtype=int):
        board.set_psfen(records[index]['sfen']);f,m=encode(board,len(embedding)==SYMMETRIC_INPUTS)
        features.append(f);materials.append(m);expected.append(reference(board,weights))
    with torch.no_grad():
        actual=model(torch.from_numpy(np.stack(features)),torch.tensor(materials,dtype=torch.float32))*600
    error=abs(actual.numpy()-np.array(expected));assert max(error)<=1.001,float(max(error))
    print(json.dumps({'passed':True,'rounding_and_ste_gradient':True,'positions':len(expected),
                      'maximum_score_difference':float(max(error)),
                      'note':'Floating training forward may differ by one unit at ties; exported integer inference has separate exact parity tests.'}))


if __name__=='__main__':main()
