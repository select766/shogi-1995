#!/usr/bin/env python3
"""Train a new small king-conditioned network and export scalar integer weights."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import struct
import sys
import time
import numpy as np
import torch
from torch import nn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from shogi1995.tiny_features import INPUTS, STRIDE


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


class Tiny(nn.Module):
    def __init__(self, width=16, hidden=16, inputs=INPUTS):
        super().__init__()
        self.width, self.hidden, self.inputs = width, hidden, inputs
        self.embedding = nn.Embedding(inputs + 1, width, padding_idx=inputs)
        self.bias = nn.Parameter(torch.full((width,), .1))
        self.fc = nn.Linear(width * 2, hidden) if hidden else None
        self.out = nn.Linear(hidden or width * 2, 1)
        nn.init.normal_(self.embedding.weight, std=.01)
        with torch.no_grad():
            self.embedding.weight[inputs].zero_()
            self.out.weight.zero_(); self.out.bias.zero_()

    def forward(self, x, material):
        acc = (self.embedding(x).sum(dim=2) + self.bias).clamp(0, 1)
        hidden = self.fc(acc.flatten(1)).clamp(0, 1) if self.fc is not None else acc.flatten(1)
        return material / 600 + self.out(hidden).squeeze(1)


def export(model, path):
    def q(tensor, scale, dtype):
        v = np.rint(tensor.detach().cpu().numpy() * scale)
        info = np.iinfo(dtype)
        if v.min() < info.min or v.max() > info.max:
            raise ValueError('quantization overflow')
        return v.astype(dtype).tobytes()
    magic=b'S95NN01\0' if model.inputs==INPUTS and model.hidden else b'S95NN02\0'
    data = magic + struct.pack('<4I', model.inputs, model.width, model.hidden, STRIDE)
    data += q(model.embedding.weight[:model.inputs], 128, '<i2')
    data += q(model.bias, 128, '<i4')
    if model.fc is not None:
        data += q(model.fc.weight, 64, '<i2')
        data += q(model.fc.bias, 8192, '<i4')
    data += q(model.out.weight, 1200, '<i2')
    data += q(model.out.bias, 153600, '<i4')
    path.write_bytes(data)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--data', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--width', type=int, default=16)
    p.add_argument('--hidden', type=int, default=16)
    p.add_argument('--epochs', type=int, default=12)
    p.add_argument('--batch', type=int, default=8192)
    p.add_argument('--seed', type=int, default=20261106)
    p.add_argument('--lr', type=float, default=.003)
    args = p.parse_args()
    if not (1 <= args.width <= 32 and 0 <= args.hidden <= 32 and args.epochs > 0 and args.batch > 0 and args.lr > 0):
        p.error('width must be 1..32, hidden 0..32 and epochs/batch/lr positive')
    if args.output.exists():
        raise RuntimeError('output already exists')
    args.output.mkdir(parents=True)
    source = json.loads((args.data / 'manifest.json').read_text()); assert source['complete']
    torch.set_num_threads(4)
    os.environ['CUBLAS_WORKSPACE_CONFIG'] = ':4096:8'
    torch.use_deterministic_algorithms(True)
    torch.manual_seed(args.seed); np.random.seed(args.seed); random.seed(args.seed)
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA required for this training run')
    device = torch.device('cuda')
    datasets = {}
    for split in ('train', 'validation'):
        for kind in ('features','targets'):
            if digest(args.data / (split + '-' + kind + '.npy')) != source['splits'][split][kind + '_sha256']:
                raise ValueError('encoded data hash differs: ' + split + ' ' + kind)
        x = torch.from_numpy(np.load(args.data / (split + '-features.npy'))).to(device=device, dtype=torch.int32)
        y = torch.from_numpy(np.load(args.data / (split + '-targets.npy'))).to(device)
        datasets[split] = x, y
    model = Tiny(args.width, args.hidden, source['inputs']).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    loss_fn = nn.BCEWithLogitsLoss()
    history = []; best = float('inf'); best_epoch = None; started = time.monotonic()
    def evaluate():
        vx, vy = datasets['validation']; total = 0.; sq = 0.
        with torch.no_grad():
            for start in range(0, len(vx), args.batch):
                target = vy[start:start+args.batch]
                logits = model(vx[start:start+args.batch], target[:, 1])
                total += loss_fn(logits, torch.sigmoid(target[:, 0] / 600)).item() * len(target)
                sq += ((logits * 600 - target[:, 0].clamp(-3000, 3000)) ** 2).sum().item()
        return total / len(vx), (sq / len(vx)) ** .5
    for epoch in range(args.epochs):
        tx, ty = datasets['train']; order = torch.randperm(len(tx), device=device)
        total = 0.
        for chunk in order.split(args.batch):
            y = ty[chunk]; logits = model(tx[chunk], y[:, 1])
            loss = loss_fn(logits, torch.sigmoid(y[:, 0] / 600))
            optimizer.zero_grad(set_to_none=True); loss.backward(); optimizer.step()
            total += loss.item() * len(chunk)
        val, rmse = evaluate()
        item = {'epoch': epoch + 1, 'train_loss': total / len(tx), 'validation_loss': val,
                'validation_clipped_rmse': rmse, 'elapsed_seconds': time.monotonic() - started}
        history.append(item); print(json.dumps(item), flush=True)
        if val < best:
            best = val; best_epoch = epoch + 1; torch.save(model.state_dict(), args.output / 'best.pt')
            export(model, args.output / 'network.bin')
        (args.output / 'history.json').write_text(json.dumps(history, indent=2) + '\n')
    report = {'complete': True, 'kind': 'king-conditioned-scalar-residual', 'width': args.width,
              'hidden': args.hidden, 'seed': args.seed, 'epochs': args.epochs, 'batch': args.batch,
              'inputs':source['inputs'],'feature_layout':source.get('feature_layout','full-king'),
              'learning_rate': args.lr, 'best_validation_loss': best,
              'best_epoch': best_epoch, 'deterministic_algorithms': True,
              'feature_index_dtype': 'int32',
              'training_manifest_sha256': hashlib.sha256((args.data / 'manifest.json').read_bytes()).hexdigest(),
              'trainer_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'feature_encoder_sha256': hashlib.sha256((ROOT / 'src/shogi1995/tiny_features.py').read_bytes()).hexdigest(),
              'torch': torch.__version__, 'device': torch.cuda.get_device_name(),
              'model_sha256': hashlib.sha256((args.output / 'network.bin').read_bytes()).hexdigest(),
              'model_bytes': (args.output / 'network.bin').stat().st_size,
              'elapsed_seconds': time.monotonic() - started}
    (args.output / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
