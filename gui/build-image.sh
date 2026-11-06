#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
deps=${SHOGI_GUI_DEPS:?Set SHOGI_GUI_DEPS to the engine repository}
export SHOGI_GUI_DEPS="$deps"
bash gui/build.sh guest
python3 - <<'PY'
import hashlib,json,pathlib,urllib.request
for item in json.loads(pathlib.Path('gui/packages.json').read_text()):
 p=pathlib.Path('.local/downloads')/item['name'];p.parent.mkdir(parents=True,exist_ok=True)
 if not p.exists(): urllib.request.urlretrieve(item['url'],p)
 if hashlib.sha256(p.read_bytes()).hexdigest()!=item['sha256']: raise SystemExit('Checksum mismatch: '+str(p))
PY
root="$PWD/.local/gui/root"
if [[ -d "$root" ]]; then chmod -R u+w "$root"; rm -rf "$root"; fi
mkdir -p "$root" .local/gui/images
# GUI owns this root and image. Never rebuild or modify the engine session's image.
cp -a --reflink=auto "$deps/.local/guest-root/." "$root/"
for pkg in tcl tk x312lib x312bin x312cfg x312fnt x312svga; do
 tar -xzf ".local/downloads/$pkg.tgz" -C "$root"
done
# Recreate known shared-library links without executing package install scripts.
python3 - "$root" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])
for folder in ['usr/lib','usr/X11R6/lib']:
 for p in (root/folder).glob('*.so.*'):
  parts=p.name.split('.so.'); link=p.with_name(parts[0]+'.so.'+parts[1].split('.')[0])
  if link!=p:
   if link.is_symlink() or link.exists(): link.unlink()
   link.symlink_to(p.name)
for name,target in [('tcl','tcl7.4'),('tk','tk4.0')]:
 p=root/'usr/lib'/name
 if p.is_symlink():p.unlink()
 if not p.exists():p.symlink_to(target)
PY
mkdir -p "$root/usr/local/lib/shogi-gui" "$root/usr/local/bin" "$root/root" "$root/etc"
ln -sfn /var/X11R6/lib "$root/usr/X11R6/lib/X11"
ln -sfn /var/X11R6/lib "$root/etc/X11"
cp .local/gui/bin/guest-tools "$root/usr/local/bin/gui-tools"
cp gui/app.tcl "$root/usr/local/lib/shogi-gui/"
cp -a gui/assets "$root/usr/local/lib/shogi-gui/"
cp .local/gui/bin/core-guest "$root/usr/local/lib/shogi-gui/core"
cp gui/engine.conf "$root/etc/shogi-gui.conf"
cp gui/guest-launch.sh "$root/usr/local/bin/shogi-gui"
cp gui/guest-start.sh "$root/etc/gui-start.sh"
cp gui/twmrc "$root/root/.twmrc"
cp gui/XF86Config "$root/etc/XF86Config"
chmod +x "$root/usr/local/bin/shogi-gui" "$root/etc/gui-start.sh"
# PID1 runs the GUI bootstrap instead of the serial USI engine.
python3 - "$deps" <<'PY'
from pathlib import Path
import sys
s=(Path(sys.argv[1])/'src/compat/guest-init.c').read_text()
s=s.replace('char *args[]={"/bin/bash",0};','char *args[]={"/bin/bash","/etc/gui-start.sh",0};')
Path('.local/gui/init.c').write_text(s)
PY
gcc -m32 -march=pentium -Os -fno-pie -no-pie -fno-stack-protector -nostdlib -static .local/gui/init.c -o "$root/sbin/init"
truncate -s 504M .local/gui/images/root.ext2
mke2fs -q -F -t ext2 -r 0 -O none -I 128 -b 1024 -N 8192 -d "$root" .local/gui/images/root.ext2
python3 - <<'PY' > .local/gui/devices.txt
for name,major,minor in [('mem',1,1),('kmem',1,2),('null',1,3),('zero',1,5),('tty',5,0),('console',4,0),('ttyS0',4,64),('psaux',10,1)]+[('tty'+str(i),4,i) for i in range(9)]:
 print('rm /dev/'+name);print('cd /dev');print('mknod '+name+' c '+str(major)+' '+str(minor))
PY
debugfs -w -f .local/gui/devices.txt .local/gui/images/root.ext2 >.local/gui/devices.log 2>&1
python3 - "$deps" <<'PY'
from pathlib import Path
import hashlib,json,sys
root=Path('.local/gui/root');deps=Path(sys.argv[1])
snapshot=[root/'shogi',root/'usr/local/lib/shogi-gui/core']
if (root/'eval').is_dir(): snapshot.extend(p for p in (root/'eval').rglob('*') if p.is_file())
files={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in snapshot}
Path('.local/gui/image-build.json').write_text(json.dumps({'engine_repository':str(deps),'files':files},indent=2)+'\n')
PY
