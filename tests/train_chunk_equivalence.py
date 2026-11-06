#!/usr/bin/env python3
"""Check resident-loader compatibility and deterministic bounded chunk training."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--data',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    args=p.parse_args()
    if args.output.exists():raise ValueError('output exists')
    args.output.mkdir(parents=True);fixture=args.output/'fixture';fixture.mkdir()
    parent=json.loads((args.data/'manifest.json').read_text())
    manifest={'complete':True,'inputs':parent['inputs'],'stride':parent['stride'],
              'feature_layout':parent.get('feature_layout','full-king'),
              'source_feature_manifest_sha256':digest(args.data/'manifest.json'),'splits':{}}
    for split,n in [('train',256),('validation',128)]:
        manifest['splits'][split]={'records':n}
        for kind in ['features','targets']:
            array=np.load(args.data/f'{split}-{kind}.npy',mmap_mode='r')
            target=fixture/f'{split}-{kind}.npy';np.save(target,np.array(array[:n],copy=True))
            manifest['splits'][split][kind+'_sha256']=digest(target)
    (fixture/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    old=ROOT/'.local/train-reference-b40cc88.py'
    old.write_bytes(subprocess.check_output(['git','show','b40cc88:scripts/train-tiny.py'],cwd=ROOT))
    runs={}
    for name,script,chunks in [('reference',old,None),('resident',ROOT/'scripts/train-tiny.py',None),
                               ('single-chunk',ROOT/'scripts/train-tiny.py',256),('chunks-a',ROOT/'scripts/train-tiny.py',100),
                               ('chunks-b',ROOT/'scripts/train-tiny.py',100)]:
        out=args.output/name
        command=[sys.executable,str(script),'--data',str(fixture.resolve()),'--output',str(out.resolve()),
                 '--width','8','--hidden','0','--epochs','2','--batch','128','--validation-interval','1','--seed','424242']
        if chunks:command+=['--chunk-records',str(chunks)]
        with (args.output/(name+'.log')).open('w') as log:subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
        runs[name]=json.loads((out/'manifest.json').read_text())
        history=json.loads((out/'history.json').read_text());assert history[-1]['examples_seen']==512
    assert runs['reference']['model_sha256']==runs['resident']['model_sha256']==runs['single-chunk']['model_sha256']
    assert runs['chunks-a']['model_sha256']==runs['chunks-b']['model_sha256']
    for name in ['chunks-a','chunks-b']:
        assert all(sorted(order)==[0,1,2] for order in runs[name]['chunk_orders'])
    result={'passed':True,'resident_backward_compatible':True,'single_chunk_matches_resident':True,
            'multiple_chunks_deterministic':True,'partial_last_chunk_covered':True,'examples_per_run':512,
            'model_sha256':{key:value['model_sha256'] for key,value in runs.items()},
            'trainer_sha256':digest(ROOT/'scripts/train-tiny.py'),'fixture_source_manifest_sha256':manifest['source_feature_manifest_sha256']}
    (args.output/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
