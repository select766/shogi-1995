#!/usr/bin/env python3
"""Archive completed real-time auxiliary matches and update graph-ready history."""
import argparse
import csv
from datetime import datetime,timezone
import fcntl
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from shogi1995.match_history import row_from_match,markdown,JST
from shogi1995.provenance import source_tree_hash


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic(path,text):
    temp=path.with_suffix(path.suffix+'.partial');temp.write_text(text);temp.replace(path)


def main():
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True)
    g.add_argument('--result',type=Path);g.add_argument('--render-only',action='store_true');args=p.parse_args()
    lock_path=ROOT/'.local/match-history.lock';lock_path.parent.mkdir(exist_ok=True)
    with lock_path.open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        history_path=ROOT/'results/match-history.json'
        history=json.loads(history_path.read_text()) if history_path.exists() else []
        if args.result:
            raw=args.result.read_bytes();report=json.loads(raw);digest=hashlib.sha256(raw).hexdigest()
            expected=report.get('measurement_sources',{}).get('src/shogi1995/match_statistics.py')
            if expected!=sha(ROOT/'src/shogi1995/match_statistics.py'):
                raise ValueError('statistics source differs; do not reinterpret an archived match')
            # Validate before creating an archive or modifying a public history.
            row=row_from_match(report,args.result.stem,'pending',digest)
            for key in ('baseline','candidate'):
                m=report[key]
                if m.get('source_commit'):
                    commit=subprocess.check_output(['git','rev-parse','--verify',m['source_commit']+'^{commit}'],cwd=ROOT,text=True).strip()
                    if (m.get('source_tree_sha256') and m.get('source_worktree_dirty') is not True
                            and source_tree_hash(commit)!=m['source_tree_sha256']):
                        raise ValueError('frozen engine source tree differs from its commit')
                    row['source_commit' if key=='candidate' else 'opponent_source_commit']=commit
            path=args.result.resolve()
            if not path.is_relative_to(ROOT/'results'):
                end=datetime.fromisoformat(report['finished_at_utc']);stamp=end.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
                safe=''.join(c if c.isalnum() or c in '-_' else '_' for c in report['candidate']['id'])
                name=safe+'-'+stamp+'-'+path.name
                archive=ROOT/'results'/end.astimezone(JST).strftime('%Y-%m-%d')/name
                archive.parent.mkdir(parents=True,exist_ok=True)
                if archive.exists() and archive.read_bytes()!=raw:raise ValueError('archive name collision')
                if not archive.exists():archive.write_bytes(raw)
                path=archive
            row.update(run_id=path.stem,result_path=str(path.relative_to(ROOT)),
                       history_sources_json=json.dumps({name:sha(ROOT/name) for name in
                           ('scripts/update-match-history.py','src/shogi1995/match_history.py')},sort_keys=True,separators=(',',':')))
            same=[r for r in history if r['run_id']==row['run_id']]
            if same and same[0]['result_sha256']!=digest:raise ValueError('run ID points to different evidence')
            history=[r for r in history if r['run_id']!=row['run_id']]+[row]
        history.sort(key=lambda r:(r['finished_at_utc'],r['run_id']))
        atomic(history_path,json.dumps(history,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
        buffer=io.StringIO(newline='')
        fields=list(dict.fromkeys(k for row in history for k in row)) if history else ['run_id','finished_at_utc','comparison_group','candidate_id','opponent_id',
            'source_commit','measurement_commit','feature_difference','score_percent','elo_difference','elo95_lower','elo95_upper',
            'elo_boundary','elo95_lower_boundary','elo95_upper_boundary','result_path','result_sha256']
        writer=csv.DictWriter(buffer,fieldnames=fields,lineterminator='\n');writer.writeheader();writer.writerows(history)
        atomic(ROOT/'results/match-history.csv',buffer.getvalue())
        atomic(ROOT/'docs/match-history.md',markdown(history))
    print(f'updated auxiliary match history: {len(history)} completed real-time runs')


if __name__=='__main__':main()
