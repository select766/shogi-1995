#!/usr/bin/env python3
"""Run the repository's unchanged scoring rules against historical GNU Shogi."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
r=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--dataset',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--backend',choices=('86box','qemu'),default='86box');p.add_argument('--compiler',choices=('old','modern'),default='old');p.add_argument('--limit',type=int);p.add_argument('--offset',type=int,default=0);a=p.parse_args()
binary=r/'bin'/('gnushogi-gcc270' if a.compiler=='old' else 'gnushogi-gcc1140')
command=[sys.executable,str(r/'usi.py'),'--backend',a.backend,'--compiler',a.compiler]
args=[sys.executable,str(r.parent/'scripts/evaluate-accuracy.py'),'--dataset',str(a.dataset.resolve()),'--output',str(a.output.resolve()),'--engine-command',json.dumps(command),'--engine-id','gnushogi-1.2p03-'+a.compiler,'--engine-sha256',hashlib.sha256(binary.read_bytes()).hexdigest(),'--engine-manifest',str(r/('manifest-'+a.compiler+'.json')),'--backend',a.backend,'--milliseconds','2000','--offset',str(a.offset),'--no-history','--feature-difference','1995 GNU Shogi, fixed 2s; historical node-based timeout, see adapter report']
if a.limit is not None:args += ['--limit',str(a.limit)]
raise SystemExit(subprocess.call(args,cwd=r.parent))
