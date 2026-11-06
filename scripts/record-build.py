#!/usr/bin/env python3
"""Record the built binaries and machine inputs without committing binaries or ROMs."""
import hashlib
import json
from pathlib import Path
import subprocess

root=Path(__file__).resolve().parents[1]
paths=['.local/guest-root/shogi','.local/legacy-libc/lib/libc.a',
       '.local/vmlinuz','.local/images/boot.img','.local/images/engine-root.ext2',
       '.local/86box/roms-master/machines/plato/1016ax1_.bio',
       '.local/86box/roms-master/machines/plato/1016ax1_.bi1',
       'config/86box/pentium100.cfg.in']
def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as file:
        while chunk:=file.read(1024*1024): h.update(chunk)
    return h.hexdigest()
report={'upstream_commit':'3a0e4fd2394e40f72fc6e2ad5aada832b4045cd9',
        'engine_edition':'YANEURAOU_ENGINE_MATERIAL','target':'PENTIUM1995',
        'files':[{ 'path':p,'sha256':digest(root/p),'bytes':(root/p).stat().st_size} for p in paths],
        'host_kernel':subprocess.check_output(['uname','-srmo'],text=True).strip()}
(root/'manifests/build.json').write_text(json.dumps(report,indent=2)+'\n')
