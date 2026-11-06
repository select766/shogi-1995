#!/usr/bin/env python3
"""Plot complete comparable runs, keeping different sample sets in separate panels."""
import argparse
import csv
import fcntl
from datetime import datetime,timedelta,timezone
import hashlib
import io
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.local/matplotlib'))
Path(os.environ['MPLCONFIGDIR']).mkdir(parents=True,exist_ok=True)
import matplotlib
matplotlib.use('Agg')
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np

JST=timezone(timedelta(hours=9))


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,default=ROOT/'results/measurement-history.csv')
    p.add_argument('--output',type=Path,default=ROOT/'results/measurement-history.svg')
    p.add_argument('--backend',choices=['86box','native','all'],default='86box')
    p.add_argument('--include-subsets',action='store_true');args=p.parse_args()
    if args.output.suffix.lower()!='.svg':raise ValueError('output must be an SVG path')
    png=args.output.with_suffix('.png');metadata_path=args.output.with_suffix('.plot.json')
    if {p.resolve() for p in (args.output,png,metadata_path)} & {args.input.resolve(),args.input.with_suffix('.json').resolve()}:
        raise ValueError('plot outputs must not overwrite measurement data')
    lock=(ROOT/'.local/measurement-history.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX)
    input_bytes=args.input.read_bytes()
    rows=list(csv.DictReader(io.StringIO(input_bytes.decode('utf-8'))))
    frozen=json.loads((ROOT/'manifests/evaluation-data.json').read_text())
    counts={item['sha256']:item['count'] for item in frozen['outputs'].values()}
    selected=[];excluded=[]
    for row in rows:
        full=(row.get('is_full_dataset','').lower()=='true') if row.get('is_full_dataset') else counts.get(row['dataset_sha256'])==int(row['positions'])
        if (args.backend!='all' and row['backend']!=args.backend) or (not args.include_subsets and not full):
            excluded.append(row['run_id']);continue
        selected.append(row)
    if not selected:raise ValueError('no complete runs match the requested condition')
    groups={}
    for row in selected:groups.setdefault(row['comparison_group'],[]).append(row)
    matplotlib.rcParams.update({'svg.hashsalt':'shogi-1995-v1','font.size':10,'text.usetex':False})
    panel_heights=[max(4.5,.36*len(items)+2) for items in groups.values()]
    fig,axes=plt.subplots(len(groups),1,figsize=(13,sum(panel_heights)),squeeze=False,
                          gridspec_kw={'height_ratios':panel_heights})
    point_data=[]
    for axis,(group,items) in zip(axes[:,0],groups.items()):
        items.sort(key=lambda row:row['finished_at_utc'])
        times=[datetime.fromisoformat(row['finished_at_utc']).astimezone(JST) for row in items]
        values=np.array([float(row['accuracy_percent']) for row in items])
        low=np.array([float(row['wilson95_lower_percent']) for row in items])
        high=np.array([float(row['wilson95_upper_percent']) for row in items])
        if not np.all((low<=values)&(values<=high)&(low>=0)&(high<=100)):
            raise ValueError('invalid accuracy or interval')
        axis.plot(times,values,color='#94a3b8',linewidth=1,linestyle='--',zorder=1)
        axis.errorbar(times,values,yerr=np.vstack([values-low,high-values]),fmt='o',color='#075985',
                      ecolor='#64748b',elinewidth=1.2,capsize=4,markersize=6,zorder=2)
        legend=[]
        for index,(row,stamp,y) in enumerate(zip(items,times,values),1):
            axis.annotate(str(index),(stamp,y),xytext=(6,6),textcoords='offset points',fontsize=9)
            legacy='*' if row['timestamp_source']!='recorded_utc' else ''
            commit=row['source_commit'][:7] or '?'
            legend.append(f"{index}. {stamp:%H:%M:%S}{legacy}  {row['engine_id']}\n    {y:.2f}%  ({row['matches']}/{row['positions']})  {commit}")
            point_data.append({key:row[key] for key in ('run_id','comparison_group','finished_at_utc','accuracy_percent',
                                                       'wilson95_lower_percent','wilson95_upper_percent','source_commit','result_sha256')})
        first=items[0]
        budget=(str(first['milliseconds'])+' ms') if first['mode']=='fixed_byoyomi' else str(first['nodes_limit'])+' nodes'
        axis.set_title(f"{first['backend']} | {first['dataset']} | {first['positions']} positions | {budget} | {group}",loc='left')
        axis.set_ylabel('Top-1 agreement (%)');axis.set_xlabel('Measurement end time (JST)')
        axis.set_ylim(max(0,float(min(low))-3),min(100,float(max(high))+3))
        axis.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d\n%H:%M',tz=JST))
        axis.grid(axis='y',alpha=.25);axis.margins(x=.08)
        axis.text(1.03,1,'\n'.join(legend),transform=axis.transAxes,va='top',ha='left',fontsize=8)
    fig.suptitle('Shogi-1995 measurement history',x=.07,y=.98,ha='left',va='top',fontsize=14)
    fig.text(.07,.015,'Wilson 95% intervals; links join identical conditions only. * Legacy times are approximate.\nAgreement is not Elo; detailed comparisons use paired bootstrap intervals.',fontsize=9)
    fig.subplots_adjust(left=.08,right=.61,top=.84 if len(groups)==1 else .93,bottom=.23 if len(groups)==1 else .13,hspace=.7)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    stamp=max(datetime.fromisoformat(row['finished_at_utc']) for row in selected).isoformat()
    svg_temp=args.output.with_suffix('.svg.partial');png_temp=png.with_suffix('.png.partial')
    fig.savefig(svg_temp,format='svg',metadata={'Date':stamp,'Creator':'shogi-1995'})
    # Matplotlib emits trailing spaces in path data; normalize generated text
    # so a regenerated graph also passes the repository whitespace check.
    svg_temp.write_text('\n'.join(line.rstrip() for line in svg_temp.read_text().splitlines())+'\n')
    fig.savefig(png_temp,format='png',dpi=144,metadata={'Software':'shogi-1995'})
    svg_temp.replace(args.output);png_temp.replace(png)
    plt.close(fig)
    result={'input_sha256':hashlib.sha256(input_bytes).hexdigest(),'plotter_sha256':sha(Path(__file__)),'matplotlib':matplotlib.__version__,
            'backend':args.backend,'include_subsets':args.include_subsets,'groups':list(groups),
            'points':point_data,'excluded_run_ids':excluded,'svg_sha256':sha(args.output),'png_sha256':sha(png)}
    temp=metadata_path.with_suffix('.json.partial');temp.write_text(json.dumps(result,indent=2)+'\n');temp.replace(metadata_path)
    print(f'plotted {len(selected)} runs in {len(groups)} comparable groups: {args.output}')


if __name__=='__main__':main()
