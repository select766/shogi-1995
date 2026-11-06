#!/usr/bin/env python3
"""Run under xvfb-run: drives the real Tk handlers, verifies modal and persistent board."""
import os
from pathlib import Path
import subprocess
import tempfile
import time
ROOT=Path(__file__).resolve().parents[2]
def wait_for(fn,timeout=5):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        try:
            value=fn()
            if value:return value
        except (FileNotFoundError,IndexError):pass
        time.sleep(.04)
    raise AssertionError('Timed out waiting for GUI state')
with tempfile.TemporaryDirectory() as d:
    d=Path(d);fifo=d/'commands';os.mkfifo(fifo);state=Path(str(fifo)+'.state')
    env=dict(os.environ,SHOGI_GUI_HOME=str(ROOT/'gui'),SHOGI_GUI_CORE=str(ROOT/'.local/gui/bin/core'),SHOGI_GUI_DEBUG=str(fifo),SHOGI_GUI_LOG=str(d/'gui.log'))
    with (d/'stderr').open('w') as err:
        p=subprocess.Popen(['wish',str(ROOT/'gui/app.tcl')],env=env,stderr=err)
        fd=os.open(fifo,os.O_RDWR)
        def send(s):os.write(fd,(s+'\n').encode());time.sleep(.08)
        def current():return state.read_text().splitlines()
        def until(test):return wait_for(lambda:current() if test(current()) else None)
        try:
            time.sleep(.3);assert p.poll() is None,(d/'stderr').read_text()
            send('setup human human 5 10');send('start')
            until(lambda s:s[0].split()[-1]=='0')
            send('click 125 323');send('click 125 281') # 7g7f
            until(lambda s:s[0].split()[-1]=='1')
            send('action');until(lambda s:'wins_resignation' in s[0])
            assert 'records 1' in current()[2]
            send('settings');send('start');until(lambda s:s[0].split()[-1]=='0')
            send('core sfen k8/9/4P4/9/9/9/9/9/4K4 b - 1')
            until(lambda s:'1,0,0' in s[0])
            send('click 209 155');send('click 209 113')
            until(lambda s:'promotion 2' in s[2])
            send('promote 1');until(lambda s:s[0].split()[-1]=='1')
            assert current()[0].split()[6].split(',')[13]=='9'
            # Actual displayed content is captured for visual inspection.
            out=ROOT/'.local/gui/host-game.png'
            subprocess.run(['import','-window','root',str(out)],check=True)
            send('action');send('settings');send('setup human human 0 0');send('start')
            until(lambda s:int(s[0].split()[4])<0)
            assert current()[0].split()[2]=='1'
            send('quit');p.wait(timeout=3)
            assert not (d/'stderr').read_text(),(d/'stderr').read_text()
            assert 'TK ERROR' not in (d/'gui.log').read_text(),(d/'gui.log').read_text()
            print('PASS: board click, records, resignation, next game, promotion modal, negative clock')
        finally:
            os.close(fd)
            if p.poll() is None:p.terminate();p.wait(timeout=3)
