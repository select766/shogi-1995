#!/usr/bin/env python3
"""Connect GNU Shogi to an explicitly selected frozen research engine."""
import argparse,hashlib,json,os,subprocess,sys
from pathlib import Path
r=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--candidate-manifest',required=True,type=Path);p.add_argument('--output-dir',required=True,type=Path);p.add_argument('--backend',choices=('86box','qemu'),default='86box');p.add_argument('--compiler',choices=('old','modern'),default='old');p.add_argument('--opening',default='7g7f 3c3d');p.add_argument('--max-plies',type=int,default=512);p.add_argument('--depth',type=int);p.add_argument('--prepare-only',action='store_true');a=p.parse_args()
if a.output_dir.exists():raise ValueError('output directory exists')
m=json.loads(a.candidate_manifest.read_text());command=list(m['command'])
if '--image' not in command:raise ValueError('requires an explicitly frozen guest image')
image=Path(command[command.index('--image')+1])
if hashlib.sha256(image.read_bytes()).hexdigest()!=m['image_sha256']:raise ValueError('candidate image hash mismatch')
a.output_dir.mkdir(parents=True);out=a.output_dir.resolve()
for name,value in [('--run-dir',str(out/'candidate-vm')),('--backend',a.backend)]:
 if name in command:command[command.index(name)+1]=value
 else:command += [name,value]
gnu=[sys.executable,str(r/'usi.py'),'--backend',a.backend,'--compiler',a.compiler,'--run-root',str(out/'gnu-vms')]
args=[sys.executable,str(r/'match.py'),'--a',json.dumps(gnu),'--b',json.dumps(command),'--b-options',json.dumps(m.get('engine_options',{})),'--output',str(out/'match.json'),'--opening',a.opening,'--max-plies',str(a.max_plies),'--backend-label','86box' if a.backend=='86box' else 'diagnostic']
if a.depth:args += ['--depth',str(a.depth)]
(out/'candidate-manifest.json').write_text(json.dumps(m,indent=2)+'\n');(out/'request.json').write_text(json.dumps({'argv':args,'candidate_manifest_source':str(a.candidate_manifest.resolve()),'gnu_manifest':json.loads((r/('manifest-'+a.compiler+'.json')).read_text())},indent=2)+'\n')
print(json.dumps(args),flush=True)
if not a.prepare_only:raise SystemExit(subprocess.call(args,env={**os.environ,'TMPDIR':'/tmp'}))
