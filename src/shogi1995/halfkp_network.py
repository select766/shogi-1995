"""Small standard-HalfKP residual networks and their scalar NN03 export."""
import struct
import numpy as np
import torch
from torch import nn
from .halfkp_features import INPUTS,STRIDE,material_initial_weights


class QuantizeSTE(torch.autograd.Function):
    @staticmethod
    def forward(ctx,value,scale,mode):
        value=value*scale
        if mode=='away':value=value.sign()*torch.floor(value.abs()+.5)
        elif mode=='positive':value=torch.floor(value+.5)
        else:value=torch.round(value)
        return value/scale

    @staticmethod
    def backward(ctx,gradient):return gradient,None,None


def quantize(value,scale,mode='even'):return QuantizeSTE.apply(value,scale,mode)


class HalfKPNetwork(nn.Module):
    def __init__(self,width=8,hidden=0,qat=False):
        super().__init__()
        if not 1<=width<=32 or not 0<=hidden<=32:raise ValueError('unsupported network dimensions')
        self.width,self.hidden,self.qat=width,hidden,qat
        self.embedding=nn.Embedding(INPUTS+1,width,padding_idx=INPUTS)
        self.bias=nn.Parameter(torch.full((width,),.1))
        self.fc=nn.Linear(width*2,hidden) if hidden else None
        self.out=nn.Linear(hidden or width*2,1)
        self.register_buffer('material_cp',torch.from_numpy(material_initial_weights()))
        nn.init.normal_(self.embedding.weight,std=.01)
        with torch.no_grad():
            self.embedding.weight[INPUTS].zero_()
            self.embedding.weight[torch.arange(81)*STRIDE]=0
            self.out.weight.zero_();self.out.bias.zero_()

    def forward(self,features):
        material=self.material_cp[features].sum(dim=2)
        material=material[:,0]-material[:,1]
        if not self.qat:
            acc=(self.embedding(features).sum(dim=2)+self.bias).clamp(0,1).flatten(1)
            hidden=self.fc(acc).clamp(0,1) if self.fc is not None else acc
            return material/600+self.out(hidden).squeeze(1)
        # Keep exported integer scales in the forward pass. In particular,
        # k/1200 * 600 in float32 can turn 24.5 CP into 24.499998 CP.
        # Float64 exactly accumulates these bounded integer products; STE
        # still supplies gradients to the original float32 parameters.
        acc=(nn.functional.embedding(features,quantize(self.embedding.weight*128,1).double(),padding_idx=INPUTS).sum(dim=2)
             +quantize(self.bias*128,1).double()).clamp(0,128).flatten(1)
        if self.fc is not None:
            acc=nn.functional.linear(acc,quantize(self.fc.weight*64,1).double(),quantize(self.fc.bias*8192,1).double())
            acc=quantize(acc/64,1,'positive').clamp(0,128)
        raw=nn.functional.linear(acc,quantize(self.out.weight*1200,1).double(),quantize(self.out.bias*153600,1).double()).squeeze(1)
        residual=quantize(raw/256,1,'away')
        return ((material.double()+residual).clamp(-12000,12000)/600).float()


def export(model,path):
    def q(value,scale,dtype):
        data=np.rint(value.detach().cpu().numpy()*scale)
        limits=np.iinfo(dtype)
        if not np.isfinite(data).all() or data.min()<limits.min or data.max()>limits.max:
            raise ValueError('network quantization overflow')
        return data.astype(dtype).tobytes()
    data=b'S95NN03\0'+struct.pack('<4I',INPUTS,model.width,model.hidden,STRIDE)
    data+=q(model.embedding.weight[:INPUTS],128,'<i2')+q(model.bias,128,'<i4')
    if model.fc is not None:data+=q(model.fc.weight,64,'<i2')+q(model.fc.bias,8192,'<i4')
    data+=q(model.out.weight,1200,'<i2')+q(model.out.bias,153600,'<i4')
    path.write_bytes(data)
