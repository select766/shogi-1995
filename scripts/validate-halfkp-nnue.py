#!/usr/bin/env python3
"""Validate an NN03 checkpoint export and integer scores on all held-out rows."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from shogi1995.halfkp_features import ACTIVE, material_initial_weights
from shogi1995.halfkp_network import HalfKPNetwork, export
from shogi1995.tiny_quant import load


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        while data := stream.read(1024 * 1024):
            h.update(data)
    return h.hexdigest()


def integer_scores(features, weights):
    """Use CPU int64 throughout; independent of the Torch forward/QAT path."""
    embedding, bias, fc, fc_bias, out, out_bias = weights
    acc = np.clip(embedding[features].sum(axis=2) + bias, 0, 128)
    acc = acc.reshape(len(features), -1)
    if len(fc):
        acc = np.clip((acc @ fc.T + fc_bias + 32) // 64, 0, 128)
    raw = acc @ out + out_bias[0]
    residual = np.where(raw >= 0, (raw + 128) // 256, -((-raw + 128) // 256))
    # Per-view material values include half CP. Preserve them until subtraction.
    material_twice = np.rint(material_initial_weights() * 2).astype(np.int64)
    values = material_twice[features].sum(axis=2)
    difference = values[:, 0] - values[:, 1]
    if np.any(difference % 2):
        raise ValueError('material difference is not an integer CP value')
    return np.clip(difference // 2 + residual, -12000, 12000)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--model', required=True, type=Path)
    p.add_argument('--validation', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--allow-unconverged', action='store_true', help='operational smoke runs only')
    args = p.parse_args()
    if args.output.exists():
        raise ValueError('preserve previous validation output')
    report = json.loads((args.model / 'manifest.json').read_text())
    source = json.loads((args.validation / 'manifest.json').read_text())
    if not report['complete'] or not source['complete']:
        raise ValueError('complete artifacts required')
    if not report['converged'] and not args.allow_unconverged:
        raise ValueError('loss saturation must precede candidate validation')
    if report['identity']['data_manifests']['validation'] != digest(args.validation / 'manifest.json'):
        raise ValueError('validation differs from training held-out set')
    for name, key in [('features.i4', 'features_sha256'), ('targets.f4', 'targets_sha256')]:
        if digest(args.validation / name) != source[key]:
            raise ValueError('validation data hash differs: ' + name)
    if digest(args.model / 'model.bin') != report['model_sha256']:
        raise ValueError('model hash differs')
    if report['identity']['model_code_sha256'] != digest(ROOT / 'src/shogi1995/halfkp_network.py'):
        raise ValueError('model implementation changed since training')
    if report['identity']['feature_code_sha256'] != digest(ROOT / 'src/shogi1995/halfkp_features.py'):
        raise ValueError('feature implementation changed since training')
    os.environ['CUBLAS_WORKSPACE_CONFIG'] = ':4096:8'
    torch.set_num_threads(4)
    torch.set_float32_matmul_precision('highest')
    torch.use_deterministic_algorithms(True)
    model = HalfKPNetwork(report['width'], report['hidden'], report['quantization_aware'])
    model.load_state_dict(torch.load(args.model / 'best.pt', map_location='cpu', weights_only=True))
    if not torch.equal(model.material_cp, torch.from_numpy(material_initial_weights())):
        raise ValueError('checkpoint material buffer differs from guest baseline')
    with tempfile.TemporaryDirectory() as folder:
        exported = Path(folder) / 'model.bin'
        export(model, exported)
        if exported.read_bytes() != (args.model / 'model.bin').read_bytes():
            raise ValueError('model is not the exact selected checkpoint export')
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA required; no implicit fallback')
    device = torch.device('cuda')
    model.to(device).eval()
    weights = load(args.model / 'model.bin')
    n = source['records']
    x = np.memmap(args.validation / 'features.i4', dtype='<i4', mode='r', shape=(n, 2, ACTIVE))
    y = np.memmap(args.validation / 'targets.f4', dtype='<f4', mode='r', shape=(n,))
    errors = []
    forward_loss = integer_loss = 0.
    outside = qat_mismatches = 0
    with torch.no_grad():
        for start in range(0, n, 4096):
            features = np.array(x[start:start + 4096], copy=True)
            target = torch.from_numpy(np.array(y[start:start + 4096], copy=True)).to(device)
            prediction = model(torch.from_numpy(features).to(device))
            integer_cpu = integer_scores(features, weights)
            integer = torch.from_numpy(integer_cpu).to(device).float()
            teacher = torch.sigmoid(target / 600)
            forward_loss += torch.nn.functional.binary_cross_entropy_with_logits(prediction, teacher, reduction='sum').item()
            integer_loss += torch.nn.functional.binary_cross_entropy_with_logits(integer / 600, teacher, reduction='sum').item()
            error = integer_cpu - prediction.cpu().numpy().astype(np.float64) * 600
            errors.append(error)
            outside += int((prediction.abs() * 600 > 12000).sum().item())
            if model.qat:
                qat_mismatches += int(np.count_nonzero(np.abs(error) > .01))
    error = np.concatenate(errors)
    result = {
        'passed': qat_mismatches == 0, 'measured_at_utc': datetime.now(timezone.utc).isoformat(),
        'positions': n, 'converged': report['converged'], 'checkpoint_export_exact_all_weights': True,
        'quantization_aware': model.qat, 'qat_integer_score_mismatches_tolerance_0_01_cp': qat_mismatches,
        'checkpoint_forward_validation_loss': forward_loss / n, 'integer_validation_loss': integer_loss / n,
        'score_quantization_rmse': float(np.sqrt(np.mean(error ** 2))),
        'score_abs_error_p99': float(np.quantile(np.abs(error), .99)),
        'score_abs_error_max': float(np.max(np.abs(error))),
        'checkpoint_forward_scores_outside_inference_clamp': outside,
        'model_sha256': digest(args.model / 'model.bin'), 'checkpoint_sha256': digest(args.model / 'best.pt'),
        'validation_manifest_sha256': digest(args.validation / 'manifest.json'),
        'validator_sha256': digest(Path(__file__)),
        'scope': 'export and quantization diagnostic; not move agreement or strength',
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)
    if not result['passed']:
        raise RuntimeError('QAT forward and independent integer scores differ')


if __name__ == '__main__':
    main()
