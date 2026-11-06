#!/usr/bin/env python3
"""Upsert completed measurements and regenerate graph-ready CSV and Japanese table."""
import argparse
import csv
import fcntl
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from shogi1995.provenance import source_tree_hash, environment_identity
JST = timezone(timedelta(hours=9))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic(path, contents):
    temp = path.with_suffix(path.suffix + '.partial')
    temp.write_text(contents); temp.replace(path)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--result', required=True, type=Path)
    p.add_argument('--engine-manifest', type=Path)
    p.add_argument('--source-commit')
    p.add_argument('--feature-difference')
    p.add_argument('--backend', choices=('86box','native','qemu'))
    p.add_argument('--historical-output', type=Path, help='Original legacy output; its mtime is only an approximate end time')
    args = p.parse_args()
    lock_path=ROOT/'.local/measurement-history.lock';lock_path.parent.mkdir(exist_ok=True)
    lock=lock_path.open('a');fcntl.flock(lock,fcntl.LOCK_EX)
    result = json.loads(args.result.read_text())
    if not result['complete'] or result['measured'] != result['total']:
        raise ValueError('only complete runs belong in the performance history')
    manifest = json.loads(args.engine_manifest.read_text()) if args.engine_manifest else {}
    if manifest and manifest['engine_sha256'] != result['engine_sha256']:
        raise ValueError('engine manifest SHA mismatch')
    backend = args.backend or result.get('backend')
    if backend is None:
        raise ValueError('legacy run needs an explicit backend')
    if result.get('finished_at_utc'):
        end = datetime.fromisoformat(result['finished_at_utc'])
        start = datetime.fromisoformat(result['started_at_utc'])
        time_source = 'recorded_utc'
    elif args.historical_output:
        old = json.loads(args.historical_output.read_text())
        if old != result:
            raise ValueError('legacy original and archived result differ')
        end = datetime.fromtimestamp(args.historical_output.stat().st_mtime, timezone.utc)
        start = end - timedelta(seconds=result['elapsed_seconds'])
        time_source = 'legacy_output_mtime_approximate'
    else:
        raise ValueError('missing measurement timestamp; specify the original historical output')
    source_commit = args.source_commit or result.get('source_commit') or manifest.get('source_commit') or ''
    if source_commit:
        source_commit = subprocess.check_output(['git','rev-parse',source_commit+'^{commit}'], cwd=ROOT, text=True).strip()
        expected_source=result.get('source_tree_sha256',manifest.get('source_tree_sha256'))
        dirty=result.get('source_worktree_dirty',manifest.get('source_worktree_dirty'))
        if expected_source and dirty is not True and source_tree_hash(source_commit)!=expected_source:
            raise ValueError('source commit does not match frozen source tree')
    measurement_commit = result.get('measurement_commit')
    if not measurement_commit:
        measurement_commit = subprocess.check_output(['git','log','-1','--format=%H','--before='+start.isoformat()], cwd=ROOT, text=True).strip()
    condition = {k:result[k] for k in ('dataset_sha256','sample_ids','mode','milliseconds','nodes','options')}
    condition['backend'] = backend
    environment=result.get('environment',environment_identity(backend))
    condition['environment_signature']=environment['signature']
    group = hashlib.sha256(json.dumps(condition,sort_keys=True,separators=(',',':')).encode()).hexdigest()[:12]
    features = args.feature_difference if args.feature_difference is not None else result.get('feature_difference','')
    if not features:
        raise ValueError('main feature difference is required')
    path = args.result.resolve()
    if not path.is_relative_to(ROOT/'results'):
        safe_engine=''.join(c if c.isalnum() or c in '-_' else '_' for c in result['engine_id'])
        stamp=end.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        archive=ROOT/'results'/end.astimezone(JST).strftime('%Y-%m-%d')/(safe_engine+'-'+stamp+'-'+path.name)
        archive.parent.mkdir(parents=True,exist_ok=True)
        if archive.exists() and archive.read_bytes()!=path.read_bytes():
            raise ValueError('archived run name already points to different evidence')
        if not archive.exists():archive.write_bytes(path.read_bytes())
        path=archive
    try:
        reference = str(path.relative_to(ROOT))
    except ValueError:
        reference = str(path)
    row = {
        'run_id': path.stem, 'started_at_utc': start.isoformat(), 'finished_at_utc': end.isoformat(),
        'finished_at_jst': end.astimezone(JST).isoformat(), 'timestamp_source': time_source,
        'engine_id': result['engine_id'], 'backend': backend, 'mode': result['mode'],
        'comparison_group': group, 'dataset': Path(result['dataset']).stem,
        'environment_signature':environment['signature'], 'environment_json':json.dumps(environment,sort_keys=True,separators=(',',':')),
        'dataset_sha256': result['dataset_sha256'],
        'sample_ids_sha256': hashlib.sha256(json.dumps(result['sample_ids'],separators=(',',':')).encode()).hexdigest(),
        'positions': result['total'], 'milliseconds': result['milliseconds'] if result['mode']=='fixed_byoyomi' else '',
        'nodes_limit': result['nodes'] or '', 'matches': result['matches'],
        'accuracy_percent': result['accuracy']*100,
        'wilson95_lower_percent': result['wilson_95']['lower']*100,
        'wilson95_upper_percent': result['wilson_95']['upper']*100,
        'rating': '', 'rating_interval': '',
        'source_commit': source_commit, 'source_commit_binding': result.get('source_commit_binding',manifest.get('source_commit_binding','historical annotation' if args.source_commit else 'unresolved')),
        'source_worktree_dirty': result.get('source_worktree_dirty',manifest.get('source_worktree_dirty','unknown')),
        'measurement_commit': measurement_commit,
        'measurement_worktree_dirty': result.get('measurement_worktree_dirty','unknown'),
        'engine_sha256': result['engine_sha256'],
        'model_sha256': result.get('guest_model_sha256',result.get('native_model_sha256',result.get('model_sha256',manifest.get('model_sha256','')))),
        'image_sha256': result.get('guest_image_sha256', result.get('image_sha256',manifest.get('image_sha256',''))) if backend in ('86box','qemu') else '',
        'source_tree_sha256': result.get('source_tree_sha256',manifest.get('source_tree_sha256','')),
        'feature_difference': features, 'errors': result['errors'], 'illegal_moves': result['illegal_moves'],
        'time_overruns': result['time_overruns'], 'options_json': json.dumps(result['options'],sort_keys=True,separators=(',',':')),
        'model_options_json': json.dumps(result.get('model_options',{}),sort_keys=True,separators=(',',':')),
        'elapsed_seconds': result['elapsed_seconds'], 'result_path': reference, 'result_sha256': sha(args.result)
    }
    history_path = ROOT/'results/measurement-history.json'
    history = json.loads(history_path.read_text()) if history_path.exists() else []
    same = [r for r in history if r['run_id']==row['run_id']]
    if same and same[0]['result_sha256'] != row['result_sha256']:
        raise ValueError('run ID already points to different evidence')
    history = [r for r in history if r['run_id']!=row['run_id']] + [row]
    history.sort(key=lambda r:(r['finished_at_utc'],r['run_id']))
    atomic(history_path, json.dumps(history,ensure_ascii=False,indent=2)+'\n')
    buffer = io.StringIO(newline=''); writer = csv.DictWriter(buffer,fieldnames=list(row),lineterminator='\n')
    writer.writeheader(); writer.writerows(history)
    atomic(ROOT/'results/measurement-history.csv',buffer.getvalue())
    lines = ['# エンジンの測定履歴','',
             '各行は完走した一回の測定。同じ `comparison_group` の行は、評価局面・標本数・時間またはノード数・共通オプション・実行環境が同じ。異なる条件の一致率を一つの成績系列として接続しない。', '',
             '[CSV](../results/measurement-history.csv) / [JSON](../results/measurement-history.json)。グラフの横軸には `finished_at_utc`、縦軸には `accuracy_percent` を使い、`comparison_group` で系列を分ける。レーティングは未測定のため空欄。', '',
             '86BoxはPentium 100 MHz・RAM 32 MiB、実時間評価は通常の秒読み2秒。NetworkDelayとNetworkDelay2はともに0。nativeの固定ノード試験はホスト診断であり、Pentiumの実時間評価とは分ける。機械構成と依存物は評価計画およびassets manifestに固定する。', '',
             '日時の†は、旧結果ファイルの更新日時と所要時間から復元した概算。以後は開始・終了UTCを測定器自身が記録する。ソースコミットが未特定の旧試作は「未確定」とし、実行ファイル・モデル・ソースツリーのSHAで追跡する。測定器のコミットとソースのコミットはCSVに別々に記録する。', '',
             '| 測定終了日時（JST） | エンジン | 条件 / 集合 | 一致数 | 一致率（Wilson 95%） | ソースcommit | 主な機能差分 |',
             '| --- | --- | --- | ---: | ---: | --- | --- |']
    for r in history:
        stamp=datetime.fromisoformat(r['finished_at_jst']).strftime('%m/%d %H:%M:%S')+('†' if r['timestamp_source']!='recorded_utc' else '')
        condition=f"{r['backend']} / {str(r['milliseconds'])+'ms' if r['mode']=='fixed_byoyomi' else str(r['nodes_limit'])+' nodes'} / {r['dataset']} {r['positions']}局面"
        commit='`'+r['source_commit'][:7]+'`' if r['source_commit'] else '未確定'
        if r['source_worktree_dirty'] is True:commit+=' +未commit差分'
        interval=f"{r['accuracy_percent']:.2f}% ({r['wilson95_lower_percent']:.2f}–{r['wilson95_upper_percent']:.2f})"
        target='../'+r['result_path'] if not r['result_path'].startswith('/') else r['result_path']
        feature=r['feature_difference'].replace('|','／').replace('\n',' ')
        lines.append(f"| {stamp} | [{r['engine_id']}]({target}) | {condition} | {r['matches']}/{r['positions']} | {interval} | {commit} | {feature} |")
    lines += ['', '反則・異常終了・時間超過の件数、モデル・バイナリ・イメージのSHA、共通設定、対応あり比較の元になる各局面の指し手はCSV/JSONおよびリンク先の明細に保存する。', '']
    atomic(ROOT/'docs/measurement-history.md','\n'.join(lines))
    print(f"updated measurement history: {row['run_id']} ({len(history)} runs)")


if __name__=='__main__':
    main()
