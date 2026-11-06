#!/usr/bin/env python3
"""Fit a small, symmetric piece-square evaluator from fresh original PSV samples."""
import argparse
import hashlib
import json
from pathlib import Path
import time

import cshogi
import numpy as np
from scipy import sparse
from scipy.sparse.linalg import lsqr

PIECE_VALUE=np.array([90,315,405,495,855,990,540,0,540,540,540,540,945,1395],dtype=np.float32)
HAND_VALUE=np.array([90,315,405,495,540,855,990],dtype=np.float32)
FEATURES=14*45+7


def matrix(path):
    records=np.memmap(path,dtype=cshogi.PackedSfenValue,mode='r')
    board=cshogi.Board();chunks=[];targets=[]
    for start in range(0,len(records),8192):
        indices=[];values=[];indptr=[0];ys=[]
        for r in records[start:start+8192]:
            board.set_psfen(r['sfen'])
            for sq,piece in enumerate(board.pieces):
                if not piece:continue
                white=piece>=16;oriented=80-sq if white else sq
                file,rank=divmod(oriented,9)
                indices.append(((piece&15)-1)*45+rank*5+min(file,8-file));values.append(-1 if white else 1)
            hands=board.pieces_in_hand
            for pt in range(7):
                count=hands[0][pt]-hands[1][pt]
                if count:indices.append(630+pt);values.append(count)
            indptr.append(len(indices))
            ys.append(int(r['score'])*(1 if board.turn==0 else -1))
        chunks.append(sparse.csr_matrix((np.asarray(values,dtype=np.float32),np.asarray(indices,dtype=np.int32),np.asarray(indptr,dtype=np.int32)),shape=(len(ys),FEATURES)))
        targets.extend(ys)
        if start%131072==0:print('encoded',start,'/',len(records),flush=True)
    x=sparse.vstack(chunks,format='csr');x.sum_duplicates();x.eliminate_zeros()
    return x,np.clip(np.asarray(targets,dtype=np.float32),-3000,3000)


def main():
    p=argparse.ArgumentParser();p.add_argument('--data',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path);p.add_argument('--alpha',type=float,default=1000)
    args=p.parse_args()
    if args.output.exists() and any(args.output.iterdir()):raise RuntimeError('output exists')
    args.output.mkdir(parents=True,exist_ok=True);started=time.monotonic()
    source=json.loads((args.data/'manifest.json').read_text());assert source['complete']
    x,y=matrix(args.data/'train.bin');vx,vy=matrix(args.data/'validation.bin')
    initial=np.concatenate([np.repeat(PIECE_VALUE,45),HAND_VALUE])
    # Robust weighting downweights extreme target scores without discarding positions.
    weights=(1+(y/1000)**2)**-.25
    weighted=x.multiply(weights[:,None]).tocsr()
    residual=(y-x@initial)*weights
    result=lsqr(weighted,residual,damp=args.alpha**.5,atol=1e-6,btol=1e-6,iter_lim=120)
    coefficients=initial+result[0]
    quantized=np.clip(np.rint(coefficients),-10000,10000).astype('<i2')
    # Header: 8 bytes magic, uint32 feature count, then little-endian int16 weights.
    import struct
    model=args.output/'psqt.bin';model.write_bytes(b'S95PSQ1\0'+struct.pack('<I',FEATURES)+quantized.tobytes())
    np.save(args.output/'coefficients.npy',coefficients)
    def metrics(pred):return {'rmse':float(np.sqrt(np.mean((pred-vy)**2))),'sign_accuracy':float(np.mean((pred>=0)==(vy>=0)))}
    report={'kind':'symmetric-psqt','training_manifest_sha256':hashlib.sha256((args.data/'manifest.json').read_bytes()).hexdigest(),
            'alpha':args.alpha,'train_records':len(y),'validation_records':len(vy),'features':FEATURES,
            'baseline':metrics(vx@initial),'trained':metrics(vx@coefficients),'quantized':metrics(vx@quantized),
            'iterations':int(result[2]),'solver_stop':int(result[1]),'model_bytes':model.stat().st_size,
            'model_sha256':hashlib.sha256(model.read_bytes()).hexdigest(),'elapsed_seconds':time.monotonic()-started}
    (args.output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
