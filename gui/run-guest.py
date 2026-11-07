#!/usr/bin/env python3
"""Own one isolated GUI VM; never acquire the USI bridge lock or mutate its disk."""
import argparse
import fcntl
import os
from pathlib import Path
import signal
import subprocess
import threading

ROOT = Path(__file__).resolve().parent.parent

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--deps', type=Path, default=os.environ.get('SHOGI_GUI_DEPS'))
    p.add_argument('--backend', choices=['86box', 'qemu'], default='86box')
    p.add_argument('--headless', action='store_true', help='QEMU diagnostics only')
    p.add_argument('--debug', action='store_true', help='QEMU serial and QMP sockets')
    p.add_argument('--engine-config', type=Path, default=ROOT/'gui/engine.conf')
    args = p.parse_args()
    if args.deps is None:
        p.error('Set SHOGI_GUI_DEPS or --deps to the engine repository')
    deps = args.deps.resolve()
    run = ROOT/'.local/gui/run';run.mkdir(parents=True, exist_ok=True)
    lock = (run/'lock').open('w')
    try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError: p.error('The GUI VM is already running')
    (run/'display').write_text(os.environ.get('DISPLAY',''))
    disk = run/'root.ext2'
    base = ROOT/'.local/gui/images/root.ext2'
    if not base.exists(): p.error('Build first: SHOGI_GUI_DEPS=... bash gui/build-image.sh')
    subprocess.run(['cp','--reflink=auto','--sparse=always',str(base),str(disk)],check=True)
    config = args.engine_config.resolve()
    # debugfs's command parser does not safely quote embedded double quotes/newlines.
    if any(c in str(config) for c in '\n\r"'): p.error('Unsupported config filename')
    with (run/'image-config.log').open('w') as log:
        for command in ['rm /etc/shogi-gui.conf', f'write "{config}" /etc/shogi-gui.conf']:
            subprocess.run(['debugfs','-w','-R',command,str(disk)],stdout=log,stderr=log,check=True)
    if args.backend == 'qemu':
        # QEMU exposes GD5446; XFree86 3.1.2 knows its compatible predecessor.
        xconfig = run/'XF86Config'
        xconfig.write_text((ROOT/'gui/XF86Config').read_text().replace('BoardName "SVGA"','BoardName "SVGA"\n    Chipset "clgd5434"'))
        with (run/'image-config.log').open('a') as log:
            for command in ['rm /etc/XF86Config', f'write "{xconfig}" /etc/XF86Config']:
                subprocess.run(['debugfs','-w','-R',command,str(disk)],stdout=log,stderr=log,check=True)
    owned = []
    if args.backend == 'qemu':
        for name in ['serial.sock','qmp.sock']:
            (run/name).unlink(missing_ok=True)
        serial = f'unix:{run}/serial.sock,server=on,wait=on' if args.debug else f'file:{run}/serial.log'
        cmd = ['qemu-system-i386','-machine','pc','-cpu','pentium','-m','32',
               '-kernel',str(deps/'.local/vmlinuz'),'-append','root=/dev/hda rw',
               '-drive',f'file={disk},format=raw,if=ide','-vga','cirrus',
               '-display','none' if args.headless else 'gtk',
               '-serial',serial,'-qmp',f'unix:{run}/qmp.sock,server=on,wait=off',
               '-monitor','none','-net','none','-no-reboot']
    else:
        if args.headless or args.debug: p.error('--headless/--debug require --backend qemu')
        vm = run/'86box';vm.mkdir(exist_ok=True)
        fifo = vm/'console'
        for suffix in ['.in','.out']:
            name = Path(str(fifo)+suffix);name.unlink(missing_ok=True);os.mkfifo(name,0o600)
            owned.append(os.open(name,os.O_RDWR | os.O_NONBLOCK))
        cfg = (deps/'config/86box/pentium100.cfg.in').read_text()
        for key,value in {'DISK':disk,'FIFO':fifo,'FLOPPY':deps/'.local/images/boot.img'}.items():
            cfg = cfg.replace('@'+key+'@',str(value))
        cfg = cfg.replace('mouse_type = none','mouse_type = ps2')
        (vm/'86box.cfg').write_text(cfg)
        cmd = [str(deps/'.local/86box/app/AppRun'),'-N','-P',str(vm),'-R',str(deps/'.local/86box/roms-master'),str(vm/'86box.cfg')]
        def drain():
            import time
            with (run/'serial.log').open('ab',buffering=0) as f:
                while True:
                    try: f.write(os.read(owned[1],8192))
                    except BlockingIOError: time.sleep(.1)
                    except OSError: return
        threading.Thread(target=drain,daemon=True).start()
    process = None
    try:
        with (run/'vm.log').open('w') as log:
            process = subprocess.Popen(cmd,stdout=log,stderr=log,start_new_session=True)
            def stop(signum,frame):
                if process.poll() is None: os.killpg(process.pid,signal.SIGTERM)
            signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
            return process.wait()
    finally:
        if process is not None and process.poll() is None:
            os.killpg(process.pid,signal.SIGKILL);process.wait()
        for fd in owned: os.close(fd)
        lock.close()

if __name__ == '__main__':
    raise SystemExit(main())
