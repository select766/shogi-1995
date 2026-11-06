#!/usr/bin/env python3
"""Compare float and exported integer predictions on the held-out tanuki data."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import numpy as np
import torch
from torch.nn import functional as F

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from shogi1995.tiny_quant import load
from shogi1995.tiny_features import INPUTS


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--model', required=True, type=Path)
    p.add_argument('--checkpoint', required=True, type=Path)
    p.add_argument('--data', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args()
    if args.output.exists():
        raise ValueError('output exists')
    embedding, bias, fc, fc_bias, out, out_bias = load(args.model)
    spec = importlib.util.spec_from_file_location('tiny_trainer', ROOT / 'scripts/train-tiny.py')
    trainer = importlib.util.module_from_spec(spec); spec.loader.exec_module(trainer)
    torch.set_num_threads(2)
    model = trainer.Tiny(embedding.shape[1], fc.shape[0])
    model.load_state_dict(torch.load(args.checkpoint, map_location='cpu', weights_only=True))
    features = np.load(args.data / 'validation-features.npy', mmap_mode='r')
    targets = np.load(args.data / 'validation-targets.npy')
    padded = np.vstack([embedding, np.zeros((1, embedding.shape[1]), dtype=embedding.dtype)])
    quantized = []; floating = []
    with torch.no_grad():
        for start in range(0, len(features), 512):
            x = np.array(features[start:start + 512], dtype=np.int64)
            acc = np.clip(padded[x].sum(axis=2) + bias, 0, 128).reshape(len(x), -1)
            hidden = np.clip((acc @ fc.T + fc_bias + 32) // 64, 0, 128)
            raw = hidden @ out + out_bias[0]
            correction = np.where(raw >= 0, (raw + 128) // 256, -((-raw + 128) // 256))
            quantized.extend(np.clip(targets[start:start + len(x), 1] + correction, -12000, 12000))
            floating.extend((model(torch.from_numpy(x), torch.from_numpy(targets[start:start + len(x), 1])) * 600).tolist())
    quantized = np.asarray(quantized); floating = np.asarray(floating)
    y = targets[:, 0]
    def metrics(prediction):
        return {'target_clipped_rmse': float(np.sqrt(np.mean((prediction - np.clip(y, -3000, 3000)) ** 2))),
                'sign_accuracy': float(np.mean((prediction >= 0) == (y >= 0))),
                'teacher_cross_entropy': float(F.binary_cross_entropy_with_logits(torch.tensor(prediction / 600), torch.sigmoid(torch.tensor(y / 600))))}
    difference = quantized - floating
    result = {'positions': len(y), 'model_sha256': hashlib.sha256(args.model.read_bytes()).hexdigest(),
              'material': metrics(targets[:, 1]), 'floating': metrics(floating), 'quantized': metrics(quantized),
              'quantization_drift': {'rmse': float(np.sqrt(np.mean(difference ** 2))),
                                     'absolute_p99': float(np.quantile(abs(difference), .99)),
                                     'absolute_max': float(max(abs(difference)))}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n'); print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
