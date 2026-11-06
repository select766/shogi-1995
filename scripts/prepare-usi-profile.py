#!/usr/bin/env python3
"""Prepare a self-configuring USI image without changing the current default image."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        while chunk:=f.read(1024*1024):h.update(chunk)
    return h.hexdigest()


def guest_file(image,path):
    return subprocess.check_output(['debugfs','-R','cat '+path,str(image)],stderr=subprocess.DEVNULL)


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path);args=p.parse_args()
    source=json.loads(args.manifest.read_text());command=source['command']
    if not source.get('complete') or set(source.get('engine_options',{}))!={'EvalFile'}:
        raise ValueError('expected a complete, model-only frozen candidate')
    image=Path(command[command.index('--image')+1]).resolve()
    if digest(image)!=source['image_sha256']:raise ValueError('source image differs from frozen manifest')
    model_path=source['engine_options'].get('EvalFile')
    if not model_path or not re.fullmatch(r'/[A-Za-z0-9_./-]+',model_path) or '..' in Path(model_path).parts:
        raise ValueError('expected a simple absolute guest model path')
    binary=guest_file(image,'/shogi');model=guest_file(image,model_path)
    if hashlib.sha256(binary).hexdigest()!=source['engine_sha256']:raise ValueError('guest binary differs')
    if hashlib.sha256(model).hexdigest()!=source['model_sha256']:raise ValueError('guest model differs')
    out=args.output.resolve()
    if out.exists():raise ValueError('output exists; never overwrite a prepared profile')
    out.mkdir(parents=True)
    target=out/'root.ext2'
    subprocess.run(['cp','--reflink=auto','--sparse=always',str(image),str(target)],check=True)
    # Use fixed local filenames in debugfs, avoiding a second shell/path parser.
    config='EvalFile '+model_path+'\n'
    (out/'guest-engine-options.txt').write_text(config)
    (out/'image-commands.txt').write_text('rm /engine_options.txt\nwrite guest-engine-options.txt /engine_options.txt\n')
    with (out/'image-edit.log').open('w') as log:
        subprocess.run(['debugfs','-w','-f','image-commands.txt',str(target)],cwd=out,stdout=log,stderr=subprocess.STDOUT,check=True)
    if guest_file(target,'/engine_options.txt')!=config.encode():raise ValueError('guest option installation failed')
    if guest_file(target,'/shogi')!=binary or guest_file(target,model_path)!=model:
        raise ValueError('engine or model changed while preparing options')
    (out/'shogi').write_bytes(binary);(out/'shogi').chmod(0o755)
    (out/'model.bin').write_bytes(model)
    profile=dict(source)
    profile.update(id=source['id']+'-usi',image_sha256=digest(target),
                   command=[str(ROOT/'run-shogi-1995.sh'),'--image',str(target)],
                   prepared_at_utc=datetime.now(timezone.utc).isoformat(),
                   preparation_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                   preparation_worktree_dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()),
                   preparation_script_sha256=digest(Path(__file__)),
                   parent_manifest_sha256=digest(args.manifest),
                   configured_guest_options={'EvalFile':model_path},
                   feature_difference=source.get('feature_difference','')+'、USI通常起動でも同じ評価ファイルを自動設定')
    (out/'manifest.json').write_text(json.dumps(profile,indent=2)+'\n')
    launcher='#!/usr/bin/env bash\nset -euo pipefail\nexec '+shlex.quote(str(ROOT/'run-shogi-1995.sh'))+' --image '+shlex.quote(str(target))+' "$@"\n'
    (out/'run.sh').write_text(launcher);(out/'run.sh').chmod(0o755)
    print(json.dumps(profile,indent=2))


if __name__=='__main__':main()
