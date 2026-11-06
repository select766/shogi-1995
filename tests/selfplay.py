#!/usr/bin/env python3
"""Short guest selfplay checked independently by python-shogi, using no training assets."""
import argparse
import json
from pathlib import Path
import queue
import random
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.local/test-python'))
import shogi


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--games', type=int, default=20)
    parser.add_argument('--backend', choices=('86box','qemu'), default='86box')
    args=parser.parse_args()
    out=ROOT / '.local/tests'
    out.mkdir(parents=True, exist_ok=True)
    report={'backend':args.backend,'nodes_per_move':128,'seed':1995,'games':[],
            'validator':'python-shogi 1.1.1','illegal_moves':0}
    messages=queue.Queue()
    start=time.monotonic()
    with (out/'selfplay-stderr.log').open('w') as err:
        proc=subprocess.Popen([str(ROOT/'run-shogi-1995.sh'),'--backend',args.backend],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,text=True,bufsize=1)
        def reader():
            for line in proc.stdout: messages.put(line.rstrip())
            messages.put(None)
        threading.Thread(target=reader,daemon=True).start()
        def send(s): proc.stdin.write(s+'\n');proc.stdin.flush()
        def wait(prefix,timeout=30):
            end=time.monotonic()+timeout
            while True:
                s=messages.get(timeout=max(.001,end-time.monotonic()))
                if s is None: raise RuntimeError('engine terminated')
                if s.startswith(prefix): return s
        rng=random.Random(1995)
        try:
            send('usi');wait('usiok',150)
            send('setoption name USI_OwnBook value false')
            send('setoption name MaxMovesToDraw value 512')
            for i in range(args.games):
                send('isready');wait('readyok',60);send('usinewgame')
                board=shogi.Board()
                moves=[]
                # Deterministic legal opening variation generated here, not imported data.
                for _ in range(6):
                    move=rng.choice(list(board.legal_moves));board.push(move);moves.append(move.usi())
                record={'game':i+1,'opening_plies':6,'moves':moves,'reason':None}
                report['games'].append(record)
                while len(moves)<512:
                    if board.is_game_over():
                        record['reason']='checkmate' if board.is_checkmate() else 'repetition_or_no_legal_move'
                        break
                    send('position startpos moves '+' '.join(moves))
                    send('go nodes 128')
                    move=wait('bestmove ')[9:].split()[0]
                    if move in ('resign','win'):
                        record['reason']=move
                        break
                    parsed=shogi.Move.from_usi(move)
                    if parsed not in board.legal_moves:
                        report['illegal_moves']+=1
                        raise RuntimeError(f'illegal move {move}, {board.sfen()}')
                    board.push(parsed);moves.append(move)
                else: record['reason']='checkmate' if board.is_checkmate() else '512_ply_limit'
                record['plies']=len(moves)
                send('gameover draw')
                print(f"game {i+1}: {len(moves)} plies, {record['reason']}",flush=True)
                report['elapsed_seconds']=time.monotonic()-start
                (out/'selfplay.json').write_text(json.dumps(report,indent=2)+'\n')
            send('quit')
            assert proc.wait(10)==0
            report['passed']=True
        finally:
            if proc.poll() is None:
                proc.terminate()
                try: proc.wait(5)
                except subprocess.TimeoutExpired: proc.kill();proc.wait()
            report['elapsed_seconds']=time.monotonic()-start
            (out/'selfplay.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='games'}))


if __name__=='__main__': main()
