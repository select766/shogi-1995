#!/usr/bin/env python3
"""Audit complete AB/BA timing blocks against their frozen full comparison."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import math
from pathlib import Path
import statistics


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(directory,comparison_path):
    comparison=json.loads(comparison_path.read_text())
    identity=json.loads((directory/'identity.json').read_text())
    count=len(identity['sample_ids']);size=identity['block_size']
    if comparison['positions']!=count or not comparison['identical_model_and_search_results']:
        raise ValueError('full comparison is not complete and identical')
    if identity.get('nodes') is None:
        raise ValueError('this audit is for fixed-node diagnostics only')
    combined={key:json.loads((directory/(key+'.json')).read_text()) for key in ('baseline','candidate')}
    for key,value in combined.items():
        source=comparison['measurements'][key]
        path=directory/(key+'.json')
        if (sha(path)!=source['sha256'] or not value['complete'] or value['sample_ids']!=identity['sample_ids']
                or value['total']!=count or value['measured']!=count or len(value['details'])!=count):
            raise ValueError('full measurement differs from comparison: '+key)
        if value['backend']!='86box' or value['mode']!='fixed_nodes':
            raise ValueError('Pentium fixed-node measurements required')
        if any(value[name]!=0 for name in ('errors','illegal_moves','time_overruns')):
            raise ValueError('full measurement operational failure')
        if value['guest_model_sha256']!=source['model_sha256'] or value['engine_sha256']!=source['engine_sha256']:
            raise ValueError('full measurement artifact differs: '+key)
    if combined['baseline']['guest_model_sha256']!=combined['candidate']['guest_model_sha256']:
        raise ValueError('different weights')
    for name in ('dataset_sha256','sample_ids','mode','milliseconds','nodes','options','backend'):
        if combined['baseline'][name]!=combined['candidate'][name]:
            raise ValueError('different paired conditions: '+name)
    if combined['baseline']['environment']['signature']!=combined['candidate']['environment']['signature']:
        raise ValueError('different paired environment')
    blocks=[];saved=[];concatenated={key:[] for key in combined}
    for index,start in enumerate(range(0,count,size)):
        paths={key:directory/f'{index:03}-{key}.json' for key in combined}
        values={key:json.loads(path.read_text()) for key,path in paths.items()}
        ids=identity['sample_ids'][start:start+size]
        for key,value in values.items():
            if not value['complete'] or value['measured']!=len(ids) or value['total']!=len(ids):
                raise ValueError('incomplete block: '+str(paths[key]))
            if any(value[name]!=0 for name in ('errors','illegal_moves','time_overruns')):
                raise ValueError('operational failure: '+str(paths[key]))
            if value['sample_ids']!=ids or [row['id'] for row in value['details']]!=ids:
                raise ValueError('block sample order differs')
            for name in ('dataset_sha256','mode','milliseconds','nodes','options','backend',
                         'guest_model_sha256','engine_sha256','guest_image_sha256'):
                if value[name]!=combined[key][name]:
                    raise ValueError('block condition/artifact differs: '+name)
            if value['environment']['signature']!=combined[key]['environment']['signature']:
                raise ValueError('block environment differs')
            if value['dataset_sha256']!=identity['dataset_sha256'] or value['nodes']!=identity['nodes']:
                raise ValueError('block differs from pair identity')
            concatenated[key]+=value['details']
        order=['baseline','candidate'] if index%2==0 else ['candidate','baseline']
        first,second=(values[key] for key in order)
        if datetime.fromisoformat(first['finished_at_utc'])>datetime.fromisoformat(second['started_at_utc']):
            raise ValueError('actual execution is not sequential AB/BA')
        block_saved=[]
        for a,b in zip(values['baseline']['details'],values['candidate']['details']):
            for field in ('id','sfen','expected','actual','final_nodes','completed_depth'):
                if a[field]!=b[field]:raise ValueError('search differs: '+field)
            if not all(math.isfinite(t) and t>0 for t in (a['host_ms'],b['host_ms'])):
                raise ValueError('invalid elapsed time')
            block_saved.append((1-b['host_ms']/a['host_ms'])*100)
        saved+=block_saved
        blocks.append({'block':index,'positions':len(ids),'execution_order':order,
                       'median_host_time_saved_percent':statistics.median(block_saved),
                       'inputs':{str(path):sha(path) for path in paths.values()}})
    for key in combined:
        if concatenated[key]!=combined[key]['details']:
            raise ValueError('full details differ from concatenated raw blocks: '+key)
    if abs(statistics.median(saved)-comparison['median_host_time_saved_percent'])>1e-12:
        raise ValueError('full median differs')
    positive=all(block['median_host_time_saved_percent']>0 for block in blocks)
    supported=bool(comparison['speedup_supported'])
    if supported!=(comparison['paired_bootstrap_95_percent']['lower']>0):
        raise ValueError('speed support flag differs from its confidence interval')
    return {'complete':True,'passed':True,'verified_at_utc':datetime.now(timezone.utc).isoformat(),
            'positions':count,'blocks':blocks,'all_block_medians_positive':positive,
            'full_comparison':{'path':str(comparison_path),'sha256':sha(comparison_path)},
            'eligible_for_ordinary_time_strength_comparison':positive and supported,
            'auditor_sha256':sha(Path(__file__)),
            'scope':'fixed-model Pentium fixed-node runtime diagnostic; not a strength result'}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--directory',required=True,type=Path)
    parser.add_argument('--comparison',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    if args.output.exists():raise ValueError('preserve previous evidence')
    result=audit(args.directory,args.comparison)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
