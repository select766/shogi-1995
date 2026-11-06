#!/usr/bin/env python3
"""Run a bounded diagnostic shell session; never use QEMU as a speed reference."""
import os
from pathlib import Path
import selectors
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
log = ROOT / '.local/probe-session.log'
command = ' '.join(sys.argv[1:]) or 'uname -a; /runtime-probe'
process = subprocess.Popen(['bash', 'scripts/run-qemu-probe.sh'],
                           stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT)
selector = selectors.DefaultSelector()
selector.register(process.stdout, selectors.EVENT_READ)
data = bytearray()
sent = False
try:
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        for key, _ in selector.select(.2):
            chunk = os.read(key.fd, 65536)
            if not chunk:
                raise RuntimeError('VM exited before probe completed')
            data.extend(chunk)
            if not sent and b'guest1995# ' in data:
                process.stdin.write((command + '; echo PROBE_DONE\n').encode())
                process.stdin.flush()
                sent = True
            if sent and b'PROBE_DONE\n' in data.replace(b'\r', b''):
                print(data.decode(errors='replace')[-12000:])
                sys.exit(0)
    raise RuntimeError('probe timed out; see .local/probe-session.log')
finally:
    log.write_bytes(data)
    selector.close()
    process.terminate()
    try:
        process.wait(3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
