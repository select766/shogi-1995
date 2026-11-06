#!/usr/bin/env python3
"""Train a compact standard HalfKP NNUE to a recorded loss plateau."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import numpy as np
import torch
from torch import nn

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from shogi1995.halfkp_features import INPUTS,ACTIVE,material_initial_weights
from shogi1995.halfkp_network import HalfKPNetwork,export


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        while data:=f.read(1024*1024):h.update(data)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--data',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path);p.add_argument('--seed',type=int,default=20261106)
    p.add_argument('--width',type=int,default=8);p.add_argument('--hidden',type=int,default=0)
    p.add_argument('--qat',action='store_true');p.add_argument('--batch',type=int,default=16384);p.add_argument('--chunk-records',type=int,default=2000000)
    p.add_argument('--lr',type=float,default=.003);p.add_argument('--max-epochs',type=int,default=100)
    p.add_argument('--min-epochs',type=int,default=40);p.add_argument('--min-examples',type=int,default=2500000000)
    p.add_argument('--resume',action='store_true');args=p.parse_args()
    if min(args.batch,args.chunk_records,args.lr,args.max_epochs,args.min_epochs)<=0 or args.min_examples<0:
        p.error('invalid training limits')
    if not 1<=args.width<=32 or not 0<=args.hidden<=32:p.error('width must be 1..32 and hidden 0..32')
    if args.max_epochs<args.min_epochs:p.error('max epochs must cover min epochs')
    if args.output.exists() and not args.resume:raise ValueError('output exists; use explicit --resume')
    if not args.output.exists() and args.resume:raise ValueError('resume output does not exist')
    os.environ['CUBLAS_WORKSPACE_CONFIG']=':4096:8';torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True);torch.manual_seed(args.seed)
    if not torch.cuda.is_available():raise RuntimeError('CUDA required; no CPU fallback')
    device=torch.device('cuda');assert float((torch.ones(1,device=device)+1).item())==2
    datasets={};identities={}
    for split in ('train','validation'):
        folder=args.data/split;manifest=json.loads((folder/'manifest.json').read_text())
        if not manifest['complete'] or manifest['inputs']!=INPUTS or manifest['split']!=split:
            raise ValueError('complete standard HalfKP data required')
        n=manifest['records']
        for filename,key,size in [('features.i4','features_sha256',n*2*ACTIVE*4),('targets.f4','targets_sha256',n*4)]:
            file=folder/filename
            if file.stat().st_size!=size or digest(file)!=manifest[key]:raise ValueError('data differs: '+split+'/'+filename)
        identities[split]=digest(folder/'manifest.json')
        x=np.memmap(folder/'features.i4',dtype='<i4',mode='r',shape=(n,2,ACTIVE))
        y=np.memmap(folder/'targets.f4',dtype='<f4',mode='r',shape=(n,))
        if split=='validation':
            x=torch.from_numpy(np.array(x,copy=True)).to(device);y=torch.from_numpy(np.array(y,copy=True)).to(device)
        datasets[split]=(x,y)
    train_manifest=json.loads((args.data/'train/manifest.json').read_text())
    if train_manifest['validation_manifest_sha256']!=identities['validation']:
        raise ValueError('train exclusion set is not this validation set')
    model=HalfKPNetwork(args.width,args.hidden,args.qat).to(device);optimizer=torch.optim.Adam(model.parameters(),lr=args.lr)
    scheduler=torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer,mode='min',factor=.3,patience=2,
        threshold=1e-5,threshold_mode='abs',min_lr=3e-6)
    loss_fn=nn.BCEWithLogitsLoss();history=[];best=float('inf');best_epoch=0;first_epoch=0;elapsed_before=0.
    source=Path(__file__).read_bytes();source_sha=hashlib.sha256(source).hexdigest()
    identity={key:value for key,value in vars(args).items() if key not in ('resume','output','data','max_epochs')}
    identity.update(data_manifests=identities,trainer_sha256=source_sha,
                    feature_code_sha256=digest(ROOT/'src/shogi1995/halfkp_features.py'),
                    model_code_sha256=digest(ROOT/'src/shogi1995/halfkp_network.py'))
    out=args.output
    if args.resume:
        previous_report=json.loads((out/'manifest.json').read_text())
        if previous_report.get('complete') and previous_report.get('converged'):
            raise ValueError('training already met the saturation rule')
        if json.loads((out/'identity.json').read_text())!=identity:raise ValueError('resume identity differs')
        state=torch.load(out/'last.pt',map_location=device,weights_only=False)
        model.load_state_dict(state['model']);optimizer.load_state_dict(state['optimizer']);scheduler.load_state_dict(state['scheduler'])
        history=state['history'];best=state['best'];best_epoch=state['best_epoch'];first_epoch=state['next_epoch']
        elapsed_before=state['elapsed_seconds'];torch.set_rng_state(state['cpu_rng'].cpu());torch.cuda.set_rng_state(state['cuda_rng'].cpu())
        if args.max_epochs<=first_epoch:raise ValueError('resume requires an epoch budget beyond the saved epoch')
    else:
        out.mkdir(parents=True);(out/'trainer-source.py').write_bytes(source)
        (out/'identity.json').write_text(json.dumps(identity,indent=2)+'\n')
    started=time.monotonic();train_x,train_y=datasets['train'];ntrain=len(train_x)
    report={'complete':False,'converged':False,'kind':'standard-HalfKP-clipped-residual-network','inputs':INPUTS,
            'width':args.width,'hidden':args.hidden,'weight_layers':3 if args.hidden else 2,'quantization_aware':args.qat,
            'train_records':ntrain,'validation_records':len(datasets['validation'][0]),'identity':identity,
            'device':torch.cuda.get_device_name(),'torch':torch.__version__,'deterministic_algorithms':True,
            'started_at_utc':previous_report['started_at_utc'] if args.resume else datetime.now(timezone.utc).isoformat(),
            'max_epochs':args.max_epochs,
            'saturation_rule':{'window_epochs':5,'validation_loss_range_max':2e-5,'train_loss_range_max':5e-5,
                               'minimum_epochs':args.min_epochs,'minimum_examples':args.min_examples,'maximum_lr':args.lr*.03},
            'shuffle':'globally qsearch-shuffled input, then epoch-seeded chunk permutation and per-chunk GPU permutation'}
    invocation={'started_at_utc':datetime.now(timezone.utc).isoformat(),
                'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                'worktree_dirty':bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip())}
    report['invocations']=(previous_report.get('invocations',[]) if args.resume else [])+[invocation]
    if args.resume:
        for name in ('initial_validation_loss','initial_validation_rmse'):
            if name in previous_report:report[name]=previous_report[name]
    def save_report():
        temp=out/'manifest.partial';temp.write_text(json.dumps(report,indent=2)+'\n');temp.replace(out/'manifest.json')
    save_report()
    def evaluate():
        x,y=datasets['validation'];total=0.;sq=0.
        with torch.no_grad():
            for start in range(0,len(x),args.batch):
                target=y[start:start+args.batch];pred=model(x[start:start+args.batch])
                total+=loss_fn(pred,torch.sigmoid(target/600)).item()*len(target)
                sq+=((pred*600-target)**2).sum().item()
        return total/len(x),(sq/len(x))**.5
    if not args.resume:report['initial_validation_loss'],report['initial_validation_rmse']=evaluate();save_report()
    converged=False
    for epoch in range(first_epoch,args.max_epochs):
        total=0.;processed=0;chunks=(ntrain+args.chunk_records-1)//args.chunk_records
        order=np.random.default_rng(args.seed+epoch).permutation(chunks).tolist()
        lr=optimizer.param_groups[0]['lr']
        for number in order:
            start=number*args.chunk_records;end=min(start+args.chunk_records,ntrain)
            x=torch.from_numpy(np.array(train_x[start:end],copy=True)).to(device)
            y=torch.from_numpy(np.array(train_y[start:end],copy=True)).to(device)
            permutation=torch.randperm(end-start,device=device)
            for indices in permutation.split(args.batch):
                pred=model(x[indices]);loss=loss_fn(pred,torch.sigmoid(y[indices]/600))
                optimizer.zero_grad(set_to_none=True);loss.backward();optimizer.step()
                total+=loss.item()*len(indices);processed+=len(indices)
            print(json.dumps({'epoch':epoch+1,'processed':processed,'total':ntrain,'elapsed_seconds':elapsed_before+time.monotonic()-started}),flush=True)
        if processed!=ntrain:raise RuntimeError('an epoch did not consume all records')
        val,rmse=evaluate();scheduler.step(val)
        row={'epoch':epoch+1,'examples_seen':(epoch+1)*ntrain,'train_loss':total/processed,
             'validation_loss':val,'validation_rmse':rmse,'learning_rate':lr,'next_learning_rate':optimizer.param_groups[0]['lr'],
             'chunk_order':order,'elapsed_seconds':elapsed_before+time.monotonic()-started}
        history.append(row);print(json.dumps(row),flush=True)
        if val<best:
            best=val;best_epoch=epoch+1;torch.save(model.state_dict(),out/'best.pt')
            export(model,out/'model.bin')
        window=history[-5:]
        if len(window)==5:
            train_range=max(r['train_loss'] for r in window)-min(r['train_loss'] for r in window)
            val_range=max(r['validation_loss'] for r in window)-min(r['validation_loss'] for r in window)
            row.update(train_loss_window_range=train_range,validation_loss_window_range=val_range)
            converged=(epoch+1>=args.min_epochs and row['examples_seen']>=args.min_examples and
                       optimizer.param_groups[0]['lr']<=args.lr*.03 and train_range<=5e-5 and val_range<=2e-5)
        (out/'history.json').write_text(json.dumps(history,indent=2)+'\n')
        state={'model':model.state_dict(),'optimizer':optimizer.state_dict(),'scheduler':scheduler.state_dict(),
               'history':history,'best':best,'best_epoch':best_epoch,'next_epoch':epoch+1,
               'elapsed_seconds':row['elapsed_seconds'],'cpu_rng':torch.get_rng_state(),'cuda_rng':torch.cuda.get_rng_state()}
        torch.save(state,out/'last.partial');(out/'last.partial').replace(out/'last.pt')
        report.update(epochs_completed=epoch+1,examples_seen=row['examples_seen'],best_validation_loss=best,best_epoch=best_epoch,
                      elapsed_seconds=row['elapsed_seconds'],converged=converged,last_epoch=row);save_report()
        if converged:break
    report.update(complete=True,converged=converged,termination_reason='loss_plateau' if converged else 'max_epochs_without_saturation',
                  model_sha256=digest(out/'model.bin'),model_bytes=(out/'model.bin').stat().st_size,
                  trainer_unchanged_at_finish=digest(Path(__file__))==source_sha,finished_at_utc=datetime.now(timezone.utc).isoformat())
    save_report();print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':main()
