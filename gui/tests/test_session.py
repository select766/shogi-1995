#!/usr/bin/env python3
"""Exercise clocks, terminal positions, repetition and single-process USI reuse."""
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import time
import unittest
ROOT=Path(__file__).resolve().parents[2]
class Session:
    def __init__(self,config=None):
        cmd=[str(ROOT/'.local/gui/bin/core'),'--debug']
        if config:cmd+=['--config',str(config)]
        self.p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,bufsize=1)
        self.q=queue.Queue()
        threading.Thread(target=lambda:[self.q.put(s.strip()) for s in self.p.stdout],daemon=True).start()
        self.until('ready')
    def send(self,s):self.p.stdin.write(s+'\n');self.p.stdin.flush()
    def until(self,prefix,predicate=lambda s:True,timeout=5):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            s=self.q.get(timeout=max(.01,end-time.monotonic()))
            if s.startswith(prefix) and predicate(s):return s.split()
        raise AssertionError(prefix)
    def state(self,check=lambda f:True):return self.until('state ',lambda s:check(s.split()))
    def close(self):
        self.send('close');self.p.wait(timeout=2);self.p.stdin.close();self.p.stdout.close()
class SessionTest(unittest.TestCase):
    def setUp(self):self.s=Session()
    def tearDown(self):self.s.close()
    def test_negative_clocks_and_increment(self):
        s=self.s;s.send('new human human 0 2');s.state();time.sleep(.15)
        s.send('state');f=s.state(lambda f:int(f[4])<0)
        self.assertEqual(f[2],'1')
        s.send('move 7g7f');s.until('move ')
        f=s.state(lambda f:int(f[11])==1)
        self.assertGreater(int(f[4]),1000);self.assertEqual(f[1],'1')
        s.send('action');f=s.state(lambda f:f[2]=='0')
        self.assertEqual(f[8],'sente_wins_resignation');self.assertEqual(f[11],'1')
    def test_repetition_and_next_game(self):
        s=self.s;s.send('new human human 300 10');s.state()
        for m in ['5i6h','5a6b','6h5i','6b5a']*3:
            s.send('move '+m);s.until('move ')
        f=s.state(lambda f:f[2]=='0');self.assertEqual(f[8],'draw_repetition')
        s.send('new human human 300 10');f=s.state(lambda f:f[2]=='1')
        self.assertEqual(f[11],'0')
    def test_perpetual_check_loses(self):
        s=self.s;s.send('new human human 300 10');s.state()
        s.send('sfen 4k4/9/5R3/9/9/9/9/9/4K4 b - 1');s.state()
        for m in ['4c5c','5a4a','5c4c','4a5a']*3:
            s.send('move '+m);s.until('move ')
        f=s.state(lambda f:f[2]=='0');self.assertEqual(f[8],'sente_loses_perpetual_check')
    def test_declare_and_forced_promotion(self):
        s=self.s;s.send('new human human 300 10');s.state()
        s.send('sfen KPPPPPPPP/PPR6/9/9/9/9/9/9/4k4 b 13P 1')
        f=s.state(lambda f:f[3]=='1');s.send('action');f=s.state(lambda f:f[2]=='0')
        self.assertEqual(f[8],'sente_wins_declaration')
    def test_engine_failure_is_visible(self):
        with tempfile.TemporaryDirectory() as d:
            cfg=Path(d)/'engine.conf';cfg.write_text('Engine=/does-not-exist\nEngineDir=/\n')
            s=Session(cfg)
            try:
                s.send('new human ai 300 10');f=s.state(lambda f:f[2]=='0')
                self.assertIn('engine_',f[8])
            finally:s.close()
    def test_fixed_byoyomi_go_command(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);engine=d/'engine';trace=d/'trace'
            engine.write_text("""#!/usr/bin/env python3
from pathlib import Path
import sys
trace=Path(__file__).with_name('trace')
for line in sys.stdin:
 line=line.strip()
 with trace.open('a') as f: f.write(line+'\\n')
 if line=='usi': print('usiok',flush=True)
 elif line=='isready': print('readyok',flush=True)
 elif line.startswith('go '): print('bestmove resign',flush=True)
""")
            engine.chmod(0o755)
            cfg=d/'engine.conf';cfg.write_text(f'Engine={engine}\nEngineDir={d}\nMatchByoyomiMs=10000\n')
            session=Session(cfg)
            try:
                session.send('new ai human 0 0')
                session.state(lambda f:f[2]=='0')
                self.assertIn('go btime 0 wtime 0 byoyomi 10000',trace.read_text())
                self.assertNotIn('setoption name MatchByoyomiMs',trace.read_text())
            finally: session.close()
    def test_single_engine_both_sides_and_restart(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);engine=d/'engine';trace=d/'trace'
            engine.write_text('''#!/usr/bin/env python3
import os,sys
from pathlib import Path
trace=Path(__file__).with_name('trace')
with trace.open('a') as f:f.write('START '+str(os.getpid())+'\\n')
moves=[]
sequence=['7g7f','3c3d','2g2f','8c8d','2f2e','8d8e']
for line in sys.stdin:
 line=line.strip()
 with trace.open('a') as f:f.write(line+'\\n')
 if line=='usi':print('usiok',flush=True)
 elif line=='isready':print('readyok',flush=True)
 elif line.startswith('position '):moves=line.split(' moves ')[1].split() if ' moves ' in line else []
 elif line.startswith('go '):
  print('bestmove '+(sequence[len(moves)] if len(moves)<len(sequence) else 'resign'),flush=True)
''');engine.chmod(0o755)
            cfg=d/'engine.conf';cfg.write_text(f'Engine={engine}\nEngineDir={d}\nUSIHash=64\n')
            s=Session(cfg)
            try:
                for count in [1,2]:
                    s.send('new ai ai 300 10');f=s.state(lambda f:f[2]=='0')
                    self.assertEqual(f[11],'6');self.assertEqual(f[8],'gote_wins_resignation')
                    text=trace.read_text();self.assertEqual(text.count('START '),count)
                    self.assertIn('setoption name USIHash value 64',text)
                    self.assertIn('binc 10000 winc 10000',text)
            finally:s.close()
if __name__=='__main__':unittest.main()
