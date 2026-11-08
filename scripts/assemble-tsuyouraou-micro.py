#!/usr/bin/env python3
"""Create a separate local 86Box image for TsuyouraOu 11 micro."""
import hashlib, json, os, shlex, shutil, subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.local/shogihome/tsuyouraou-micro-v1'
BUILD = ROOT / '.local/tsuyouraou-micro'
PACKAGES = ('aaa_base', 'bash', 'ldso', 'shlibs', 'bin', 'sh_utils')
def digest(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''): h.update(chunk)
    return h.hexdigest()
if OUT.exists(): raise SystemExit(f'Output already exists: {OUT}')
inputs = {'shogi': BUILD / 'yaneuraou-pentium-rebuild', 'sbin/init': ROOT / '.local/release-assets/denryu-halfkp-v1/guest-init-pentium1995', 'eval/nn.bin': BUILD / 'eval/nn.bin', 'eval/progress.bin': BUILD / 'eval/progress.bin', 'eval/eval_options.txt': BUILD / 'eval/eval_options.txt'}
expected = {'eval/nn.bin': '7f9545dbf73b87acf312146daabf59c4f17d0845c87d587fa19caed51707dddb', 'eval/progress.bin': 'a2d18f0564639c945b5d6469e9b437cd64a526ad4fbcef02ab1d8f547d08e5f1', 'sbin/init': '0164b73503a213aeb93f249f1950f12da8c00c54a5b059eab53dcce3948c26c9'}
for target, sha in expected.items():
    if digest(inputs[target]) != sha: raise ValueError('unexpected input: ' + target)
assets = {x['name']: x for x in json.loads((ROOT / 'manifests/assets.json').read_text())['assets']}
for package in PACKAGES:
    name = package + '.tgz'
    if digest(ROOT / '.local/downloads' / name) != assets[name]['sha256']: raise ValueError('unexpected package: ' + name)
OUT.mkdir(parents=True); stage = OUT / 'root'; stage.mkdir()
for package in PACKAGES:
    subprocess.run(['tar', '-xzf', str(ROOT / '.local/downloads' / (package + '.tgz')), '-C', str(stage)], check=True)
for name in ('dev','proc','tmp','sbin','bin','lib','eval'): (stage / name).mkdir(exist_ok=True)
for name, target in [('bin/sh','bash'),('lib/ld-linux.so.1','ld-linux.so.1.7.3'),('lib/libc.so.5','libc.so.5.0.9')]:
    path=stage/name; path.unlink(missing_ok=True); path.symlink_to(target)
for target, source in inputs.items():
    dest=stage/target; shutil.copyfile(source,dest); dest.chmod(0o755 if target in ('shogi','sbin/init') else 0o644)
options={'Threads':'1','USI_Hash':'2','MaxMovesToDraw':'512','EnteringKingRule':'CSARule27','USI_Ponder':'false','NetworkDelay':'120','NetworkDelay2':'1120','USI_OwnBook':'false','BookFile':'no_book','FV_SCALE':'24'}
(OUT/'engine-defaults.json').write_text(json.dumps(options,indent=2)+'\n')
image=OUT/'root.ext2'
with image.open('xb') as f: f.truncate(504*1024*1024)
with (OUT/'image-build.log').open('x') as log:
    subprocess.run(['mke2fs','-q','-F','-t','ext2','-r','0','-O','none','-I','128','-b','1024','-N','4096','-d',str(stage),str(image)],stdout=log,stderr=subprocess.STDOUT,check=True)
    subprocess.run(['debugfs','-w','-f','/dev/stdin',str(image)],input='cd /dev\nmknod ttyS0 c 4 64\nmknod console c 4 0\nmknod null c 1 3\nmknod zero c 1 5\nmknod tty c 5 0\n',text=True,stdout=log,stderr=subprocess.STDOUT,check=True)
for target, source in inputs.items():
    data=subprocess.check_output(['debugfs','-R','cat /'+target,str(image)],stderr=subprocess.DEVNULL)
    if hashlib.sha256(data).hexdigest()!=digest(source): raise ValueError('image mismatch: '+target)
name='shogi-1995 TsuyouraOu 11 micro (Pentium 100MHz)'
launcher='#!/usr/bin/env bash\nset -euo pipefail\nprofile_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"\nrepo_dir="$(cd -- "$profile_dir"/../../.. && pwd)"\nexec "$repo_dir/run-shogi-1995.sh" --image "$profile_dir/root.ext2" --engine-defaults "$profile_dir/engine-defaults.json" --engine-name '+shlex.quote(name)+' "$@"\n'
(OUT/'run.sh').write_text(launcher); (OUT/'run.sh').chmod(0o755)
manifest={'id':'tsuyouraou-micro','created_utc':datetime.now(timezone.utc).isoformat(),'image_sha256':digest(image),'payload_sha256':{k:digest(v) for k,v in inputs.items()},'configured_guest_options':options,'usi_name':name,'book_included':False}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(OUT/'run.sh')
