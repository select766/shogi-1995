#!/usr/bin/env python3
"""Boot real Linux 1.2.13 + Tk 4.0, drive GUI and the unchanged repository engine."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('guest_debug',ROOT/'gui/guest-debug.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
run=ROOT/'.local/gui/run'
p=subprocess.Popen([sys.executable,str(ROOT/'gui/run-guest.py'),'--deps',os.environ['SHOGI_GUI_DEPS'],'--backend','qemu','--headless','--debug'])
g=None
try:
    time.sleep(.3)
    end=time.monotonic()+10
    while True:
        try:g=mod.Guest();break
        except (FileNotFoundError,ConnectionRefusedError):
            if time.monotonic()>end:raise
            time.sleep(.1)
    print(g.read_until())
    log=g.command('/usr/local/bin/gui-tools cat /tmp/shogi-gui-launch.log')
    assert not log,log
    g.screenshot(run/'guest-settings.ppm')
    print(g.command('read pid < /tmp/shogi-gui.pid; kill $pid; /bin/touch /tmp/shogi-gui-debug'))
    time.sleep(.5)
    g.command('/usr/local/bin/shogi-gui >/tmp/debug-launch.log 2>&1 &')
    time.sleep(.5)
    g.gui('setup human human 5 10');g.gui('start')
    def wait_state(predicate,timeout=10):
        end=time.monotonic()+timeout;state=''
        while time.monotonic()<end:
            state=g.state()
            if state.startswith('state ') and predicate(state.splitlines()):return state
            if 'engine_disconnected' in state:break
            time.sleep(.15)
        log=g.command('/usr/local/bin/gui-tools cat /tmp/shogi-gui.log');(run/'guest-test-log.txt').write_text(log)
        raise AssertionError(state+'\n'+log[-5000:]+'\n'+g.command('/usr/local/bin/gui-tools cat /tmp/debug-launch.log')+'\nDIRECT ENGINE:\n'+g.command('echo usi | /shogi')+'\nMEMORY:\n'+g.command('/usr/local/bin/gui-tools cat /proc/meminfo'))
    wait_state(lambda s:s[0].split()[-1]=='0')
    g.gui('click 125 323');time.sleep(.2);g.gui('click 125 281')
    wait_state(lambda s:s[0].split()[-1]=='1')
    g.screenshot(run/'guest-game.ppm')
    g.gui('action');wait_state(lambda s:'wins_resignation' in s[0])
    g.gui('settings');g.gui('start');wait_state(lambda s:s[0].split()[-1]=='0')
    g.gui('core sfen k8/9/4P4/9/9/9/9/9/4K4 b - 1');time.sleep(.3)
    g.gui('click 209 155');time.sleep(.2);g.gui('click 209 113')
    wait_state(lambda s:'promotion 2' in s[2]);g.screenshot(run/'guest-promotion.ppm')
    g.gui('promote 1');wait_state(lambda s:s[0].split()[-1]=='1')
    g.gui('action');wait_state(lambda s:'wins_resignation' in s[0]);g.gui('settings')
    g.gui('setup ai ai 0 1');g.gui('start')
    state=wait_state(lambda s:int(s[0].split()[-1])>=6,timeout=45)
    g.gui('action');wait_state(lambda s:s[0].split()[2]=='0')
    log=g.command('/usr/local/bin/gui-tools cat /tmp/shogi-gui.log')
    assert log.count('ENGINE spawn pid=')==1,log[-4000:]
    assert 'TK ERROR' not in log,log[-4000:]
    assert 'USI> go btime' in log and 'binc 1000 winc 1000' in log
    assert 'loaded: /eval/model.bin' in log,log[-5000:]
    ai_plies=int(state.splitlines()[0].split()[-1])
    # Both mixed assignments use the same GUI/USI path, with one process per game.
    g.gui('settings');g.gui('setup human ai 0 1');g.gui('start')
    wait_state(lambda s:s[0].split()[8]=='playing')
    g.gui('click 125 323');time.sleep(.2);g.gui('click 125 281')
    wait_state(lambda s:int(s[0].split()[-1])>=2)
    g.gui('action');wait_state(lambda s:s[0].split()[2]=='0')
    g.gui('settings');g.gui('setup ai human 0 1');g.gui('start')
    wait_state(lambda s:int(s[0].split()[-1])>=1)
    g.gui('click 293 155');time.sleep(.2);g.gui('click 293 197')
    wait_state(lambda s:int(s[0].split()[-1])>=2)
    g.gui('action');wait_state(lambda s:s[0].split()[2]=='0')
    log=g.command('/usr/local/bin/gui-tools cat /tmp/shogi-gui.log')
    assert log.count('ENGINE spawn pid=')==3
    assert 'TK ERROR' not in log
    (run/'guest-test-log.txt').write_text(log)
    (run/'guest-test-result.json').write_text(json.dumps({'status':'pass','ai_plies':ai_plies,'engine_processes_per_game':1,'mixed_assignments_tested':2,'engine_build':json.loads((ROOT/'.local/gui/image-build.json').read_text())},indent=2)+'\n')
    print('PASS: guest Tk4 board, promotion, next game; repository engine AI vs AI and both mixed assignments (one process per game)')
finally:
    if g:g.close()
    p.terminate()
    try:p.wait(timeout=5)
    except subprocess.TimeoutExpired:p.kill();p.wait()
