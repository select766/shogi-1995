#!/usr/bin/env python3
"""Replace only model bytes in a verified frozen USI runtime, without staging changes."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from shogi1995.provenance import source_tree_hash


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def guest_file(image, path):
    return subprocess.check_output(['debugfs', '-R', 'cat ' + path, str(image)], stderr=subprocess.DEVNULL)


def package(runtime_manifest, model, output, name, feature_difference):
    if not re.fullmatch(r'[A-Za-z0-9_-]+', name):
        raise ValueError('invalid profile name')
    snapshot = runtime_manifest.read_bytes()
    source = json.loads(snapshot)
    options = source.get('configured_guest_options', {})
    if (not source.get('complete') or set(options) != {'EvalFile'}
            or source.get('engine_options') != options or source.get('source_worktree_dirty') is not False):
        raise ValueError('complete self-configuring runtime with committed source required')
    if source_tree_hash(source['source_commit']) != source['source_tree_sha256']:
        raise ValueError('runtime source commit binding differs')
    model_path = options['EvalFile']
    if not re.fullmatch(r'/[A-Za-z0-9_./-]+', model_path) or '..' in Path(model_path).parts:
        raise ValueError('invalid guest model path')
    command = source['command']
    if len(command) != 3 or command[:2] != [str(ROOT / 'run-shogi-1995.sh'), '--image']:
        raise ValueError('expected explicit frozen bridge image command')
    image = Path(command[2]).resolve()
    if digest(image) != source['image_sha256']:
        raise ValueError('frozen runtime image hash differs')
    binary = guest_file(image, '/shogi')
    old_model = guest_file(image, model_path)
    config = guest_file(image, '/engine_options.txt')
    if (hashlib.sha256(binary).hexdigest() != source['engine_sha256']
            or hashlib.sha256(old_model).hexdigest() != source['model_sha256']
            or config != ('EvalFile ' + model_path + '\n').encode()):
        raise ValueError('frozen runtime contents differ')
    model_hash = digest(model)
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    target = output / 'root.ext2'
    subprocess.run(['cp', '--reflink=auto', '--sparse=always', str(image), str(target)], check=True)
    if digest(target) != source['image_sha256']:
        raise ValueError('runtime changed during copy')
    shutil.copyfile(model, output / 'model.bin')
    if digest(output / 'model.bin') != model_hash:
        raise ValueError('model changed during copy')
    (output / 'image-commands.txt').write_text('rm ' + model_path + '\nwrite model.bin ' + model_path + '\n')
    with (output / 'image-edit.log').open('x') as log:
        subprocess.run(['debugfs', '-w', '-f', 'image-commands.txt', str(target)], cwd=output,
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    if (guest_file(target, '/shogi') != binary or guest_file(target, '/engine_options.txt') != config
            or hashlib.sha256(guest_file(target, model_path)).hexdigest() != model_hash):
        raise ValueError('model replacement changed runtime or installed different weights')
    (output / 'shogi').write_bytes(binary)
    (output / 'shogi').chmod(0o755)
    (output / 'runtime-manifest.json').write_bytes(snapshot)
    report = dict(source)
    report.update(id=name + '-usi', image_sha256=digest(target), model_sha256=model_hash,
                  model_bytes=(output / 'model.bin').stat().st_size, model_origin=str(model.resolve()),
                  command=[str(ROOT / 'run-shogi-1995.sh'), '--image', str(target)],
                  feature_difference=feature_difference,
                  prepared_at_utc=datetime.now(timezone.utc).isoformat(),
                  preparation_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  preparation_worktree_dirty=bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip()),
                  preparation_script_sha256=digest(Path(__file__)),
                  parent_manifest_sha256=hashlib.sha256(snapshot).hexdigest(),
                  runtime_origin_manifest=str(runtime_manifest.resolve()),
                  runtime_reused_without_rebuilding=True)
    (output / 'manifest.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    (output / 'run.sh').write_text('#!/usr/bin/env bash\nset -euo pipefail\nexec '
                                 + shlex.quote(str(ROOT / 'run-shogi-1995.sh')) + ' --image '
                                 + shlex.quote(str(target)) + ' "$@"\n')
    (output / 'run.sh').chmod(0o755)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime-manifest', required=True, type=Path)
    parser.add_argument('--model', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--name', required=True)
    parser.add_argument('--feature-difference', required=True)
    args = parser.parse_args()
    print(json.dumps(package(args.runtime_manifest, args.model, args.output, args.name,
                             args.feature_difference), indent=2, ensure_ascii=False))
