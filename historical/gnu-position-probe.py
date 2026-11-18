#!/usr/bin/env python3
"""Print GNU Shogi's iterative-deepening log for given positions (fresh process each).  usage: out_dir seconds "moves..." ..."""
import argparse, importlib.util, sys, re
from pathlib import Path
ROOT = Path('/home/select766/shogi/shogi-1995')
spec = importlib.util.spec_from_file_location('usi_adapter', ROOT / 'historical/usi.py')
usi = importlib.util.module_from_spec(spec); spec.loader.exec_module(usi)
usi.emit = lambda s: None
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
sec = int(sys.argv[2])
for pos in sys.argv[3:]:
    args = argparse.Namespace(backend='native', native_binary=ROOT / '.local/native-gnushogi/src/gnushogir', run_root=out, compiler='old', research_root=ROOT)
    ad = usi.Adapter(args)
    ad.set_position('position startpos moves ' + pos)
    ad.go(f'go btime 0 wtime 0 byoyomi {sec*1000}')
    log = (ad.t.run / 'transport.log').read_text(errors='replace')
    ad.t.close()
    i = log.rfind('Move#')
    print('=== ', pos)
    print('\n'.join(l for l in log[i:].splitlines() if re.match(r'^\s*\d+[.&+\-]\s', l) or 'timeout' in l or 'My move' in l))
