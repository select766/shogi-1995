#!/usr/bin/env python3
"""Compare GNU Shogi time-control commands on opening positions where it blundered.

The recorded hirate game (recording-gnu-gote-02) used `level 0 0:10`
(fixed 10 s per move, TCflag=false).  GNU timed out in the middle of depth 10
after the first root move failed low and selected another root move by a
fail-low upper bound.  This script searches the same positions again with
`level 0 0:10` and with `level 1 0:10` (one move per 10 s time control,
TCflag=true, flag.onemove), and records the move, depth and GNU's own PV log.
"""
import argparse, importlib.util, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('usi_adapter', ROOT / 'historical/usi.py')
usi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(usi)

GAME = '2g2f 3c3d 2f2e 5a6b 2e2d 2b3c'.split()
MODES = ['level 0 0:10', 'level 1 0:10']

p = argparse.ArgumentParser()
p.add_argument('--output', type=Path, default=ROOT / 'results/gnu-timecontrol-audit')
p.add_argument('--trials', type=int, default=3)
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=True)

emitted = []
usi.emit = lambda s: emitted.append(s)
current_mode = {'v': None}
orig_cmd = usi.Transport.cmd
def cmd(self, text, *args, **kw):
    # The adapter sends `level 0 m:ss` and then `depth 29`.  GNU's `depth`
    # command recomputes TCflag = !(MaxSearchDepth > 0), which would cancel a
    # time-control `level`.  So send `depth` first and the selected level last.
    if text.startswith('level 0 '):
        return b''
    out = orig_cmd(self, text, *args, **kw)
    if text.startswith('depth'):
        out += orig_cmd(self, current_mode['v'], *args, **kw)
    return out
usi.Transport.cmd = cmd

results = []
# Replay GNU's own moves of the recorded game in one process, as in the game
# (the relay keeps the GNU process and sends `new` + the position each move).
for mode in MODES:
    for trial in range(a.trials):
        current_mode['v'] = mode
        args = argparse.Namespace(backend='native', native_binary=ROOT / '.local/native-gnushogi/src/gnushogir',
                                  run_root=a.output, compiler='old', research_root=ROOT)
        ad = usi.Adapter(args)
        for ply in (1, 3, 5):
            emitted.clear()
            start = len((ad.t.run / 'transport.log').read_bytes()) if ad.t else 0
            ad.set_position('position startpos moves ' + ' '.join(GAME[:ply]))
            ad.go('go btime 0 wtime 0 byoyomi 10000')
            log = (ad.t.run / 'transport.log').read_bytes()[start:].decode(errors='replace')
            pv = [l for l in log.splitlines() if re.match(r'^\s*\d+[.&+\-]\s', l) or l.strip() == 'timeout']
            info = [e for e in emitted if e.startswith('info depth')][0].split()
            r = {'ply': ply, 'game_move': GAME[ply], 'mode': mode, 'trial': trial,
                 'bestmove': [e for e in emitted if e.startswith('bestmove')][0].split()[1],
                 'depth': int(info[2]), 'time_ms': int(info[4]), 'nodes': int(info[6]), 'pv_log_tail': pv[-12:]}
            results.append(r)
            print(json.dumps({k: v for k, v in r.items() if k != 'pv_log_tail'}), flush=True)
            (a.output / 'result.json').write_text(json.dumps(results, indent=1, ensure_ascii=False) + '\n')
        ad.t.close()
