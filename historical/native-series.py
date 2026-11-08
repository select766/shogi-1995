#!/usr/bin/env python3
"""Paired 10-second games: native GNU versus a frozen 86Box engine."""
import argparse, hashlib, json, random, sys, time
from pathlib import Path
import cshogi
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from shogi1995.usi import Engine
from shogi1995.sessions import COMMON
from shogi1995.match_rules import Referee


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, default=ROOT/'manifests/halfkp-fixed-w8-h0-128m-radix-v1-candidate.json')
    parser.add_argument('--dataset', type=Path, default=ROOT/'private/gokaku/taya36.sfen')
    parser.add_argument('--gnu-binary', type=Path, default=ROOT/'.local/native-gnushogi/src/gnushogir')
    parser.add_argument('--pairs', type=int, default=50)
    parser.add_argument('--start-pair', type=int, default=0, help='zero-based offset in the reproducibly sampled pairs')
    parser.add_argument('--end-pair', type=int, help='exclusive offset in sampled pairs')
    parser.add_argument('--seed', type=int, default=20261107)
    parser.add_argument('--opening-lines', help='comma-separated one-based line numbers; overrides sampling')
    parser.add_argument('--backend', choices=('86box', 'qemu'), default='86box')
    parser.add_argument('--depth', type=int, help='diagnostic only')
    parser.add_argument('--max-plies', type=int, default=256, help='diagnostic limit; default includes opening moves')
    args = parser.parse_args()
    if args.output.exists(): raise ValueError('output already exists')
    manifest = json.loads(args.manifest.read_text())
    image = Path(manifest['command'][manifest['command'].index('--image')+1])
    if sha(image) != manifest['image_sha256']: raise ValueError('image hash mismatch')
    lines = args.dataset.read_text().splitlines()
    if args.pairs < 1 or args.pairs > len(lines): raise ValueError('invalid pair count')
    if args.opening_lines:
        indices=[int(x)-1 for x in args.opening_lines.split(',')]
        if len(indices)!=len(set(indices)) or any(x<0 or x>=len(lines) for x in indices):raise ValueError('invalid line numbers')
        end=len(indices)
    else:
        indices = random.Random(args.seed).sample(range(len(lines)), args.pairs)
        end=args.end_pair if args.end_pair is not None else args.pairs
        if not 0 <= args.start_pair < end <= args.pairs: raise ValueError('invalid pair slice')
        indices=indices[args.start_pair:end]
    args.output.mkdir(parents=True)
    out = args.output.resolve()
    binary=args.gnu_binary.resolve()
    candidate=list(manifest['command']) + ['--run-dir',str(out/'vm'), '--backend',args.backend]
    native=[sys.executable,str(ROOT/'historical/usi.py'),'--backend','native','--native-binary',str(binary),'--run-root',str(out/'gnu')]
    (out/'gnu').mkdir()
    report={'complete':False,'backend':args.backend,'depth':args.depth,'seconds_per_move':10,'max_total_plies':args.max_plies,'seed':args.seed,'pair_slice':[args.start_pair,end],'dataset_sha256':sha(args.dataset),'manifest':manifest,'gnu_binary_sha256':sha(binary),'selected_line_numbers':[i+1 for i in indices],'games':[]}
    def save():
        p=out/'series.tmp'; p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');p.replace(out/'series.json')
    save()
    engines=[]
    try:
        native_options=dict(COMMON)
        candidate_options={**COMMON,**manifest.get('engine_options',{}),'MaxMovesToDraw':args.max_plies,'NetworkDelay':0,'NetworkDelay2':0}
        engines.append(Engine(native,ROOT,out/'gnu-usi',native_options))
        engines.append(Engine(candidate,ROOT,out/'yaneuraou-usi',candidate_options))
        for index in indices:
            opening=lines[index].split()
            if opening[:2]!=['startpos','moves']: raise ValueError('invalid opening format')
            for gnu_side in (0,1):
                game={'opening_line':index+1,'gnu_side':gnu_side,'moves':[],'outcome':None,'status':'running'}
                report['games'].append(game)
                record=out/f"game-{len(report['games']):03}.usi"
                referee=Referee(cshogi.STARTING_SFEN,1000000000,0,args.max_plies)
                def save_game():
                    record.write_text('startpos moves'+(' '+' '.join(referee.moves) if referee.moves else '')+'\n')
                    save()
                try:
                    for move in opening[2:]:
                        outcome=referee.accept(move,0)
                        if outcome is not None: raise ValueError('opening ends game: '+str(outcome))
                    save_game()
                    for e in engines: e.reset()
                    outcome=referee.terminal()
                    while outcome is None:
                        side=referee.board.turn
                        e=engines[0 if side==gnu_side else 1]
                        command=f'go depth {args.depth}' if args.depth else 'go btime 0 wtime 0 byoyomi 10000'
                        result=e.search_position(referee.position_command(),command,120 if args.depth else 90)
                        referee.remaining[side]=1000000000
                        outcome=referee.accept(result['actual'],result['host_ms'])
                        game['moves'].append({'side':side,**result})
                        save_game()
                    if outcome['reason'] in ('illegal_move','illegal_declaration','time_forfeit'): raise ValueError(str(outcome))
                    game['outcome']=outcome; game['status']='complete'
                except (RuntimeError,TimeoutError,OSError,ValueError) as exc:
                    game['status']='abnormal'; game['error']=str(exc);save_game()
                    raise RuntimeError('series stopped after abnormal game; inspect logs') from exc
                save_game()
                print(json.dumps({'game':len(report['games']),'line':index+1,'gnu_side':gnu_side,'outcome':outcome},ensure_ascii=False),flush=True)
        report['complete']=True
    finally:
        for e in reversed(engines):e.close()
        save()

if __name__=='__main__': main()
