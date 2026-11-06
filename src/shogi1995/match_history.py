"""Graph-ready auxiliary match rows; group only identical opponent/settings."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math

from .match_statistics import match_summary

JST=timezone(timedelta(hours=9))


def row_from_match(report,run_id,result_path,result_sha256):
    if (not report['complete'] or report.get('fatal_error') or report['mode']!='guest_fischer_auxiliary'
            or report.get('backend')!='86box' or report['nodes'] is not None):
        raise ValueError('completed real-time Pentium auxiliary match required')
    games=report['games'];expected=report['expected_games'];ids=report['opening_ids']
    if not ids or len(set(ids))!=len(ids) or expected!=len(ids)*2 or len(games)!=expected:
        raise ValueError('opening pairs or planned game count differ')
    if any('outcome' not in game for game in games):raise ValueError('unfinished game')
    if [game['opening_id'] for game in games]!=[key for key in ids for _ in (0,1)]:
        raise ValueError('opening order differs from plan')
    calibration=report['clock_calibration'];samples=calibration.get('samples',[])
    if (not calibration.get('passed') or len(samples)!=6
            or {(s['repeat'],s['engine']) for s in samples}!={(r,e) for r in range(3) for e in range(2)}):
        raise ValueError('six independent clock calibration samples required')
    for sample in samples:
        if (not all(math.isfinite(sample[k]) for k in ('requested_ms','host_ms','guest_ms'))
                or not sample['passed'] or sample['requested_ms']!=5000
                or abs(sample['host_ms']-5000)>100
                or abs(sample['host_ms']-sample['guest_ms'])>100):
            raise ValueError('clock calibration exceeds planned2% tolerance')
    score=match_summary(games,rating_enabled=True)
    if report['score']!=score:raise ValueError('stored match score differs from independent recount')
    start=datetime.fromisoformat(report['started_at_utc']);end=datetime.fromisoformat(report['finished_at_utc'])
    if start.utcoffset() is None or end.utcoffset() is None or end<start:raise ValueError('invalid timestamps')
    baseline=report['baseline'];candidate=report['candidate'];options=report['common_engine_options']
    if (options['NetworkDelay']!=report['network_delay'] or options['NetworkDelay2']!=report['network_delay2']):
        raise ValueError('network delay metadata differs')
    if not baseline['complete'] or not candidate['complete']:raise ValueError('unfrozen engine')
    for m in (baseline,candidate):
        if not m.get('engine_sha256') or not m.get('image_sha256'):raise ValueError('missing frozen guest hashes')
        if not m.get('source_commit'):raise ValueError('engine source commit required')
        if any(k not in ('EvalFile','NetworkDelay','NetworkDelay2') and options.get(k)!=v
               for k,v in m.get('engine_options',{}).items()):
            raise ValueError('per-engine options differ from recorded common settings')
    features=candidate.get('feature_difference','').strip()
    if not features:raise ValueError('candidate feature difference required')
    condition={'backend':'86box','environment_signature':report['environment']['signature'],
               'opponent_engine_sha256':baseline['engine_sha256'],'opponent_model_sha256':baseline.get('model_sha256',''),
               'opponent_image_sha256':baseline['image_sha256'],'dataset_sha256':report['dataset_sha256'],
               'opening_ids':ids,'color_order':[g['candidate_color'] for g in games],
               'initial_ms':report['initial_ms'],'increment_ms':report['increment_ms'],
               'max_plies':report['max_plies'],'options':options,'mode':report['mode']}
    group=hashlib.sha256(json.dumps(condition,sort_keys=True,separators=(',',':')).encode()).hexdigest()[:12]
    interval=score['score_rate_95'] or {};elo_interval=score['elo_difference_95'] or {}
    failures=score['operational_failures']
    row={'run_id':run_id,'started_at_utc':start.astimezone(timezone.utc).isoformat(),
         'finished_at_utc':end.astimezone(timezone.utc).isoformat(),'finished_at_jst':end.astimezone(JST).isoformat(),
         'candidate_id':candidate['id'],'opponent_id':baseline['id'],'backend':'86box','mode':report['mode'],
         'comparison_group':group,'environment_signature':report['environment']['signature'],
         'dataset_sha256':report['dataset_sha256'],'opening_pairs':len(ids),'games':score['games'],
         'initial_ms':report['initial_ms'],'increment_ms':report['increment_ms'],'max_plies':report['max_plies'],
         'wins':score['wins'],'draws':score['draws'],'losses':score['losses'],'score_percent':score['score_rate']*100,
         'score95_lower_percent':interval['lower']*100 if interval else '',
         'score95_upper_percent':interval['upper']*100 if interval else '',
         'elo_difference':score['elo_difference_estimate'] if score['elo_difference_estimate'] is not None else '',
         'elo_boundary':score['elo_difference_boundary'] or '',
         'elo95_lower':elo_interval.get('lower') if elo_interval.get('lower') is not None else '',
         'elo95_upper':elo_interval.get('upper') if elo_interval.get('upper') is not None else '',
         'elo95_lower_boundary':elo_interval.get('lower_boundary') or '',
         'elo95_upper_boundary':elo_interval.get('upper_boundary') or '',
         'rating_eligible':score['rating_eligible'],'operational_pass':score['operational_pass'],
         'candidate_operational_failures':sum(failures['candidate'].values()),
         'opponent_operational_failures':sum(failures['baseline'].values()),
         'source_commit':candidate.get('source_commit',''),'opponent_source_commit':baseline.get('source_commit',''),
         'measurement_commit':report['measurement_commit'],'measurement_worktree_dirty':report.get('measurement_worktree_dirty','unknown'),
         'engine_sha256':candidate['engine_sha256'],'model_sha256':candidate.get('model_sha256',''),
         'image_sha256':candidate['image_sha256'],'opponent_engine_sha256':baseline['engine_sha256'],
         'opponent_model_sha256':baseline.get('model_sha256',''),'opponent_image_sha256':baseline['image_sha256'],
         'feature_difference':features,'options_json':json.dumps(options,sort_keys=True,separators=(',',':')),
         'conditions_json':json.dumps(condition,sort_keys=True,separators=(',',':')),
         'measurement_sources_json':json.dumps(report['measurement_sources'],sort_keys=True,separators=(',',':')),
         'elapsed_seconds':report.get('elapsed_seconds',''),
         'interval_method':score['interval_method'],'limitation':score['limitation'],
         'result_path':result_path,'result_sha256':result_sha256}
    return row


def markdown(history):
    lines=['# 補助対局の測定履歴','','[CSV](../results/match-history.csv) / [JSON](../results/match-history.json) / [一致率の履歴](measurement-history.md)。',
           '', '完走したPentium実時間対局を記録する。横軸は`finished_at_utc`、縦軸は`elo_difference`または`score_percent`を使い、`comparison_group`が同じ行だけを接続する。Eloは固定相手・同じ持ち時間に対する換算差で、リーグのレーティングではない。',
           '', '先後2局を1組とする保守的な95%区間。全勝・全敗で有限値が得られない端点はCSVの境界ラベルで示す。運用異常のある完走結果は記録するが、Eloは付けない。固定ノードの動作試験と未完了対局は含めない。',
           '', '| 終了日時（JST） | 候補 / 相手 | 条件 | 勝–分–敗 | 得点率 | Elo換算差（95%） | ソースcommit | 主な機能差分 |',
           '| --- | --- | --- | --- | ---: | --- | --- | --- |']
    def number(value,boundary=''):
        if boundary:return '+∞' if boundary=='+infinity' else '−∞'
        return f'{value:+.1f}' if value!='' else '未算出'
    for row in history:
        stamp=datetime.fromisoformat(row['finished_at_jst']).strftime('%m/%d %H:%M:%S')
        target='../'+row['result_path'];elo='運用異常により除外'
        if row['rating_eligible']:
            elo=number(row['elo_difference'],row['elo_boundary'])+' ('+number(row['elo95_lower'],row['elo95_lower_boundary'])+'〜'+number(row['elo95_upper'],row['elo95_upper_boundary'])+')'
        feature=row['feature_difference'].replace('|','／').replace('\n',' ')
        lines.append(f"| {stamp} | [{row['candidate_id']}]({target}) / {row['opponent_id']} | {row['initial_ms']/1000:g}s + {row['increment_ms']/1000:g}s / {row['games']}局 | {row['wins']}–{row['draws']}–{row['losses']} | {row['score_percent']:.2f}% | {elo} | `{row['source_commit'][:7]}` | {feature} |")
    if not history:lines+=['','実時間の最終20局はまだ未実施。測定値は登録されていない。']
    return '\n'.join(lines)+'\n'
