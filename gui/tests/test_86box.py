#!/usr/bin/env python3
"""Run under xvfb-run. Verify the normal 86Box launch path and guest GUI startup."""
import os
from pathlib import Path
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[2];run=ROOT/'.local/gui/run'
p=subprocess.Popen([sys.executable,str(ROOT/'gui/run-guest.py'),'--deps',os.environ['SHOGI_GUI_DEPS']])
try:
    end=time.monotonic()+90
    captured=False
    while time.monotonic()<end:
        if p.poll() is not None:raise AssertionError((run/'vm.log').read_text())
        if not captured and time.monotonic()>end-55:
            subprocess.run(['import','-window','root',str(run/'86box-boot.png')],check=True);captured=True
        try:
            if 'gui1995# ' in (run/'serial.log').read_text(errors='replace'):break
        except FileNotFoundError:pass
        time.sleep(.5)
    else:raise AssertionError('Guest boot timeout: '+(run/'serial.log').read_text(errors='replace'))
    fifo=run/'86box/console.in'
    fd=os.open(fifo,os.O_WRONLY|os.O_NONBLOCK)
    os.write(fd,b'/usr/local/bin/gui-tools cat /tmp/shogi-gui-launch.log\necho GUI86BOX_OK\n');os.close(fd)
    time.sleep(3)
    text=(run/'serial.log').read_text(errors='replace')
    assert 'GUI86BOX_OK' in text,text
    assert 'Error' not in text and 'failed' not in text,text
    subprocess.run(['import','-window','root',str(run/'86box-desktop.png')],check=True)
    print('PASS: 86Box Pentium 100 MHz / 32 MiB guest GUI startup')
finally:
    p.terminate()
    try:p.wait(timeout=5)
    except subprocess.TimeoutExpired:p.kill();p.wait()
