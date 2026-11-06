#!/usr/bin/env python3
"""Warm-history auxiliary games with independent guest clocks and a host referee."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import cshogi
from shogi1995.match_rules import Referee
from shogi1995.sessions import Pair, digest


def utc():
    return datetime.now(timezone.utc).isoformat()


def main():
    def interrupted(signum,frame):
        raise SystemExit(128+signum)
    signal.signal(signal.SIGTERM,interrupted)
    p=argparse.ArgumentParser()
    p.add_argument('--baseline',required=True,type=Path)
    p.add_argument('--candidate',required=True,type=Path)
    p.add_argument('--dataset',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    p.add_argument('--openings',type=int,default=10)
    p.add_argument('--initial-ms',type=int,default=180000)
    p.add_argument('--increment-ms',type=int,default=2000)
    p.add_argument('--max-plies',type=int,default=512)
    p.add_argument('--network-delay',type=int,default=120)
    p.add_argument('--network-delay2',type=int,default=1120)
    p.add_argument('--native',action='store_true',help='Host fixed-node operational test only')
    p.add_argument('--nodes',type=int,help='Operational smoke test; never a real-time strength result')
    args=p.parse_args()
    if args.output.exists():
        raise ValueError('output exists; never discard a started game')
    if args.native and args.nodes is None:
        p.error('native is permitted only for fixed-node operational tests')
    if min(args.openings,args.initial_ms,args.max_plies)<=0 or min(args.increment_ms,args.network_delay,args.network_delay2)<0:
        p.error('invalid game settings')
    if args.nodes is not None and args.nodes<=0:
        p.error('nodes must be positive')
    records=[json.loads(line) for line in args.dataset.read_text().splitlines() if line.strip()]
    if args.openings>len(records):
        raise ValueError('not enough fixed opening positions')
    manifests=[args.baseline.resolve(),args.candidate.resolve()]
    report={'complete':False,'started_at_utc':utc(),'measurement_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'baseline':json.loads(args.baseline.read_text()),'candidate':json.loads(args.candidate.read_text()),
            'dataset_sha256':digest(args.dataset),'opening_ids':[r['id'] for r in records[:args.openings]],
            'initial_ms':args.initial_ms,'increment_ms':args.increment_ms,'max_plies':args.max_plies,
            'network_delay':args.network_delay,'network_delay2':args.network_delay2,
            'mode':'fixed_nodes_operational' if args.nodes else 'guest_fischer_auxiliary',
            'nodes':args.nodes,'expected_games':args.openings*2,'games':[]}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    def save():
        games=[g for g in report['games'] if 'outcome' in g]
        wins=sum(g['candidate_result']=='win' for g in games)
        draws=sum(g['candidate_result']=='draw' for g in games)
        losses=sum(g['candidate_result']=='loss' for g in games)
        report['score']={'games':len(games),'wins':wins,'draws':draws,'losses':losses,
                         'score_rate':(wins+.5*draws)/len(games) if games else None}
        temp=args.output.with_suffix('.partial');temp.write_text(json.dumps(report,indent=2)+'\n');temp.replace(args.output)
    save();start=time.monotonic()
    run=ROOT/'.local/match-runs'/args.output.stem
    try:
        with Pair(manifests,run,args.output.with_suffix('.logs'),args.native) as pair:
            report['clock_calibration']=pair.calibrate(cshogi.STARTING_SFEN,native=args.native)
            save()
            if not args.native and not report['clock_calibration']['passed']:
                raise RuntimeError('two-VM clock calibration failed; auxiliary strength games are invalid')
            for engine in pair.engines:
                engine.send(f'setoption name NetworkDelay value {args.network_delay}')
                engine.send(f'setoption name NetworkDelay2 value {args.network_delay2}')
            for index in range(args.openings*2):
                opening=records[index//2];candidate_color=index%2
                # Engines remain [baseline,candidate]; each position is played with both assignments.
                by_color=[pair.engines[1 if side==candidate_color else 0] for side in range(2)]
                for engine in pair.engines:
                    engine.reset()
                referee=Referee(opening['sfen'],args.initial_ms,args.increment_ms,args.max_plies)
                game={'game':index+1,'opening_id':opening['id'],'start_sfen':opening['sfen'],
                      'candidate_color':candidate_color,'started_at_utc':utc(),'moves':[]}
                report['games'].append(game);save()
                outcome=referee.terminal()
                while outcome is None:
                    side=referee.board.turn
                    command=f'go nodes {args.nodes}' if args.nodes else referee.go_command()
                    timeout=120 if args.nodes else referee.remaining[side]/1000+5
                    try:
                        result=by_color[side].search_position(referee.position_command(),command,max(5,timeout))
                    except (TimeoutError,RuntimeError,OSError) as error:
                        outcome={'winner':1-side,'reason':'engine_failure','error':str(error)}
                        break
                    game['moves'].append({'side':side,**result})
                    outcome=referee.accept(result['actual'],result['host_ms'])
                    game['remaining_ms']=list(referee.remaining);save()
                game['outcome']=outcome
                game['candidate_result']='draw' if outcome['winner'] is None else 'win' if outcome['winner']==candidate_color else 'loss'
                game['finished_at_utc']=utc();save()
                for side,engine in enumerate(by_color):
                    result='draw' if outcome['winner'] is None else 'win' if outcome['winner']==side else 'lose'
                    engine.send('gameover '+result)
                print(f"game {index+1}/{args.openings*2}: candidate {game['candidate_result']} ({outcome['reason']})",flush=True)
                if outcome['reason']=='engine_failure':
                    raise RuntimeError('engine failure; preserve partial run instead of continuing with broken engine')
            report['complete']=True
    except BaseException as error:
        report['fatal_error']=str(error)
        raise
    finally:
        report['finished_at_utc']=utc();report['elapsed_seconds']=time.monotonic()-start;save()
    print(json.dumps(report['score'],indent=2))


if __name__=='__main__':
    main()
