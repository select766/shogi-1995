#!/usr/bin/env python3
"""Run original Dhrystone 2.1 in the project's isolated 86Box Linux guest."""
import hashlib
import os
from pathlib import Path
import select
import re
import shutil
import signal
import subprocess
import sys
import time
import importlib.util

ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
run = ROOT / '.local/pentium100-dhry'
run.mkdir(parents=True, exist_ok=True)
source = Path(sys.argv[1] if len(sys.argv) > 1 else '/tmp/shogi-dhry-c').resolve()
iterations = int(sys.argv[2]) if len(sys.argv) > 2 else 2_000_000
if not 1 <= iterations <= 100_000_000:
    raise SystemExit('iterations must be between 1 and 100000000')
expected = '038a7e9169787125c3451a6c941f3aca5db2d2f3863871afcdce154ef17f4e3e'
if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
    raise SystemExit('Unexpected Dhrystone archive SHA-256')
src = run / 'src'
src.mkdir(exist_ok=True)
subprocess.run(['sh', str(source)], cwd=src, check=True)
cc = ROOT / '.local/i486-linux-musl-cross/bin/i486-linux-musl-gcc'
legacy = ROOT / '.local/legacy-libc'
exe = run / 'dhry'
subprocess.run([str(cc), '-march=pentium', '-O2', '-fno-pie', '-DTIME', '-static', '-no-pie', '-nostartfiles', str(legacy/'crt1.o'), '-I'+str(legacy/'include'), '-L'+str(legacy/'lib'), str(src/'dhry_1.c'), str(src/'dhry_2.c'), '-o', str(exe)], check=True)
print('binary_sha256', hashlib.sha256(exe.read_bytes()).hexdigest(), flush=True)
vm = run/'vm'
vm.mkdir(exist_ok=True)
if (ROOT/'.local/vm/nvr').exists():
    shutil.copytree(ROOT/'.local/vm/nvr', vm/'nvr', dirs_exist_ok=True)
disk = vm/'root.ext2'
shutil.copyfile(ROOT/'.local/images/probe-root.ext2', disk)
subprocess.run(['debugfs', '-w', '-R', 'write '+str(exe)+' /dhry', str(disk)], check=True, stdout=subprocess.DEVNULL)
fifo = vm/'usi'
for suffix in ('.in', '.out'):
    path = Path(str(fifo)+suffix)
    path.unlink(missing_ok=True)
    os.mkfifo(path, 0o600)
writer = os.open(str(fifo)+'.in', os.O_RDWR|os.O_NONBLOCK)
reader = os.open(str(fifo)+'.out', os.O_RDWR|os.O_NONBLOCK)
config = (ROOT/'config/86box/pentium100.cfg.in').read_text()
for key, val in {'DISK':disk,'FIFO':fifo,'FLOPPY':ROOT/'.local/images/boot.img'}.items():
    config = config.replace('@'+key+'@', str(val))
config = config.replace('63, 16, 1024, 0, ide', '32, 16, 128, 0, ide')
(vm/'86box.cfg').write_text(config)
for name in ('display', 'xauthority'):
    (run/name).unlink(missing_ok=True)
spec = importlib.util.spec_from_file_location('bridge', ROOT/'src/bridge/main.py')
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
bridge.RUN = run
log = (run/'emulator.log').open('wb')
proc = subprocess.Popen(['xvfb-run','-a','bash','scripts/launch-86box.sh',str(run)], stdout=log, stderr=log, start_new_session=True)
buffer = bytearray()
sent = False
start = time.monotonic()
next_escape = start+8
try:
    while time.monotonic()-start < 240 + iterations * 3 / 100_000:
        if proc.poll() is not None:
            raise RuntimeError('86Box exited; see emulator.log')
        if time.monotonic() >= next_escape:
            bridge.bios_escape()
            next_escape = time.monotonic()+5
        if select.select([reader], [], [], .1)[0]:
            data = os.read(reader, 65536)
            buffer.extend(data)
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()
            if not sent and b'guest1995# ' in buffer:
                os.write(writer, f"echo BENCH_START; for n in 1 2 3; do echo {iterations} | /dhry; done; echo BENCH_DONE\n".encode())
                sent = True
            if sent and b'BENCH_DONE\n' in buffer.replace(b'\r',b''):
                break
    else:
        raise RuntimeError('timeout; see emulator.log')
finally:
    (run/'serial.txt').write_bytes(buffer)
    os.killpg(proc.pid, signal.SIGTERM)
    proc.wait(timeout=10)
    os.close(reader)
    os.close(writer)
    log.close()

result = buffer.decode('ascii', errors='replace').replace('\r', '')
for value, expected_value in [('Int_Glob', '5'), ('Bool_Glob', '1'), ('Ch_1_Glob', 'A'), ('Ch_2_Glob', 'B'), ('Arr_1_Glob[8]', '7'), ('Arr_2_Glob[8][7]', str(iterations + 10)), ('Int_1_Loc', '5'), ('Int_2_Loc', '13'), ('Int_3_Loc', '7'), ('Enum_Loc', '1')]:
    found = re.findall(r'^' + re.escape(value) + r':\s*(\S+)', result, re.M)
    if found != [expected_value] * 3:
        raise SystemExit('Unexpected benchmark output for ' + value + ': ' + repr(found))
if len(re.findall(r'Dhrystones per Second:\s+[0-9.]+', result)) != 3:
    raise SystemExit('Expected three completed measurements')
