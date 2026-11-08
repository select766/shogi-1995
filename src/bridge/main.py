#!/usr/bin/env python3
"""Expose a guest-only engine over USI. 86Box is the default; QEMU is diagnostic."""
import argparse
import ctypes
import fcntl
import json
import os
import re
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / '.local/run'


def load_engine_defaults(path):
    if path is None:
        return {}
    raw = json.loads(path.read_text())
    if not isinstance(raw, dict):
        raise ValueError('engine defaults must be an option/value object')
    values = {}
    for key, value in raw.items():
        if not re.fullmatch(r'[A-Za-z0-9_]+', key) or not isinstance(value, (str, int, bool)):
            raise ValueError('invalid engine default')
        encoded = str(value).lower() if isinstance(value, bool) else str(value)
        if not encoded or any(c in encoded for c in '\r\n\0'):
            raise ValueError('invalid engine default value')
        values[key] = encoded
    return values


def advertise_defaults(line, defaults, engine_name=None):
    if engine_name is not None and line.startswith('id name '):
        return 'id name ' + engine_name
    match = re.match(r'option name (.*?) type ', line)
    if match and match[1] in defaults:
        return re.sub(r' default .*?(?= (?:min|max|var) |$)',
                      lambda _: ' default ' + defaults[match[1]], line, count=1)
    return line


def bios_escape():
    """Dismiss first-boot CMOS notice on this process's isolated X server only."""
    if not (RUN / 'display').exists() or not (RUN / 'xauthority').exists():
        return
    os.environ['XAUTHORITY'] = (RUN / 'xauthority').read_text().strip()
    x = ctypes.CDLL('libX11.so.6')
    t = ctypes.CDLL('libXtst.so.6')
    ptr = ctypes.c_void_p
    x.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x.XOpenDisplay.restype = ptr
    display = x.XOpenDisplay((RUN / 'display').read_text().strip().encode())
    if not display:
        return
    try:
        x.XStringToKeysym.argtypes = [ctypes.c_char_p]
        x.XStringToKeysym.restype = ctypes.c_ulong
        x.XKeysymToKeycode.argtypes = [ptr, ctypes.c_ulong]
        x.XKeysymToKeycode.restype = ctypes.c_uint
        key = x.XKeysymToKeycode(display, x.XStringToKeysym(b'Escape'))
        t.XTestFakeMotionEvent.argtypes = [ptr, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ulong]
        t.XTestFakeMotionEvent(display, -1, 150, 150, 0)
        t.XTestFakeKeyEvent.argtypes = [ptr, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
        t.XTestFakeKeyEvent(display, key, 1, 0)
        t.XTestFakeKeyEvent(display, key, 0, 0)
        x.XFlush.argtypes = [ptr]
        x.XFlush(display)
    finally:
        x.XCloseDisplay.argtypes = [ptr]
        x.XCloseDisplay(display)


def main():
    global RUN
    def interrupted(signum, frame):
        raise SystemExit(128 + signum)
    signal.signal(signal.SIGTERM, interrupted)
    parser = argparse.ArgumentParser()
    parser.add_argument('--backend', choices=('86box', 'qemu'), default='86box')
    parser.add_argument('--boot-timeout', type=float, default=120)
    parser.add_argument('--image', type=Path, default=ROOT / '.local/images/engine-root.ext2')
    parser.add_argument('--engine-defaults', type=Path,
                        help='Initial USI settings, overridable by the GUI; never rewrites go commands')
    parser.add_argument('--engine-name', help='USI display name for an explicitly selected engine profile')
    parser.add_argument('--run-dir', type=Path, default=RUN,
                        help='Isolated VM state, serial FIFOs, logs and lock directory')
    args = parser.parse_args()
    if args.engine_name is not None and (not args.engine_name.strip() or any(c in args.engine_name for c in '\r\n\0')):
        parser.error('engine name must be a nonempty single line')
    engine_defaults = load_engine_defaults(args.engine_defaults)
    os.chdir(ROOT)
    RUN = args.run_dir.resolve()
    RUN.mkdir(parents=True, exist_ok=True)
    lock = (RUN / 'engine.lock').open('w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise RuntimeError('another shogi-1995 engine is running')
    image = args.image.resolve()
    if not image.exists():
        raise RuntimeError('guest image missing; run scripts/setup.sh first')
    log = (RUN / 'transport.log').open('wb')
    events = (RUN / 'usi.log').open('w', buffering=1)
    selector = selectors.DefaultSelector()
    process = None
    owned_fds = []
    try:
        if args.backend == 'qemu':
            process = subprocess.Popen([
                'qemu-system-i386', '-machine', 'pc', '-cpu', 'pentium', '-m', '32',
                '-kernel', '.local/vmlinuz', '-append', 'root=/dev/hda rw',
                '-drive', f'file={image},format=raw,if=ide', '-snapshot',
                '-display', 'none', '-serial', 'stdio', '-monitor', 'none',
                '-no-reboot', '-net', 'none'], stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=log, start_new_session=True)
            reader, writer = process.stdout.fileno(), process.stdin.fileno()
        else:
            vm = RUN / 'vm'
            vm.mkdir(exist_ok=True)
            disk = vm / 'root.ext2'
            subprocess.run(['cp', '--reflink=auto', '--sparse=always', str(image), str(disk)], check=True)
            fifo = vm / 'usi'
            for suffix in ('.in', '.out'):
                p = Path(str(fifo) + suffix)
                if p.exists():
                    p.unlink()
                os.mkfifo(p, 0o600)
            writer = os.open(str(fifo) + '.in', os.O_RDWR | os.O_NONBLOCK)
            reader = os.open(str(fifo) + '.out', os.O_RDWR | os.O_NONBLOCK)
            owned_fds.extend((writer, reader))
            config = (ROOT / 'config/86box/pentium100.cfg.in').read_text()
            for key, value in {'DISK': disk, 'FIFO': fifo, 'FLOPPY': ROOT / '.local/images/boot.img'}.items():
                config = config.replace('@' + key + '@', str(value))
            (vm / '86box.cfg').write_text(config)
            for name in ('display', 'xauthority'):
                (RUN / name).unlink(missing_ok=True)
            process = subprocess.Popen(['xvfb-run', '-a', 'bash', 'scripts/launch-86box.sh',str(RUN)],
                stdout=log, stderr=log, start_new_session=True)
        os.set_blocking(reader, False)
        os.set_blocking(writer, False)
        selector.register(reader, selectors.EVENT_READ, 'guest')
        selector.register(sys.stdin.fileno(), selectors.EVENT_READ, 'host')
        incoming = {'guest': bytearray(), 'host': bytearray()}
        outgoing = bytearray()
        queued = []
        ready = False
        boot_started = time.monotonic()
        next_escape = boot_started + 8
        stop_sent = quit_sent = None
        next_write = 0.0

        def send(line):
            outgoing.extend(line.encode() + b'\n')
            events.write(f'{time.monotonic():.3f} > {line}\n')

        def command(line):
            nonlocal stop_sent, quit_sent
            if line.startswith('go ponder'):
                raise RuntimeError('ponder is not supported by this build')
            if line.startswith('setoption name USI_Ponder') and line.endswith('true'):
                print('info string Ponder is disabled in shogi-1995', flush=True)
                return
            if line == 'go' or line.startswith('go '):
                stop_sent = None
            if line == 'stop':
                stop_sent = time.monotonic()
            if line == 'quit':
                quit_sent = time.monotonic()
            send(line)

        while True:
            now = time.monotonic()
            if process.poll() is not None:
                if quit_sent is not None:
                    return 0
                raise RuntimeError(f'VM exited ({process.returncode}); see {log.name}')
            if not ready:
                if now - boot_started > args.boot_timeout:
                    raise RuntimeError(f'guest startup timed out; see {log.name}')
                if args.backend == '86box' and now >= next_escape:
                    bios_escape()
                    next_escape = now + 5
            if stop_sent is not None and now - stop_sent > 3:
                raise RuntimeError('guest did not return bestmove after stop')
            if quit_sent is not None and now - quit_sent > 1:
                return 0
            if outgoing and now >= next_write:
                try:
                    # No hardware flow control: pace input below 115200 baud so
                    # a burst cannot overrun the emulated UART or old tty driver.
                    count = os.write(writer, outgoing[:32])
                    del outgoing[:count]
                    next_write = now + count * 10 / 115200 * 1.25
                except BlockingIOError:
                    pass
            for key, _ in selector.select(.005):
                kind = key.data
                chunk = os.read(key.fd, 65536)
                if not chunk:
                    if kind == 'host':
                        if ready:
                            command('quit')
                        else:
                            return 0
                        selector.unregister(key.fd)
                        continue
                    raise RuntimeError('guest transport closed')
                if kind == 'guest':
                    log.write(chunk)
                    log.flush()
                buf = incoming[kind]
                buf.extend(chunk)
                if len(buf) > 1024 * 1024:
                    raise RuntimeError('protocol line exceeds 1 MiB')
                while b'\n' in buf:
                    raw, _, rest = buf.partition(b'\n')
                    buf[:] = rest
                    line = raw.decode('utf-8', errors='replace').rstrip('\r')
                    if kind == 'host':
                        if ready:
                            command(line)
                        else:
                            queued.append(line)
                    elif not ready:
                        if line == 'SHOGI1995_ENGINE_READY':
                            ready = True
                            print(f'shogi-1995: guest ready after {now-boot_started:.1f}s ({args.backend})', file=sys.stderr)
                            for name, value in engine_defaults.items():
                                command(f'setoption name {name} value {value}')
                            for item in queued:
                                command(item)
                            queued.clear()
                    else:
                        events.write(f'{now:.3f} < {line}\n')
                        if line.startswith('bestmove '):
                            stop_sent = None
                        if line == 'guest shell exited; restart VM to retry':
                            if quit_sent is not None:
                                return 0
                            raise RuntimeError('guest engine exited unexpectedly')
                        print(advertise_defaults(line, engine_defaults, args.engine_name), flush=True)
    finally:
        selector.close()
        if process is not None and process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(3)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        for fd in owned_fds:
            os.close(fd)
        log.close()
        events.close()
        lock.close()


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (RuntimeError, OSError, ValueError) as error:
        print(f'shogi-1995: {error}', file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
