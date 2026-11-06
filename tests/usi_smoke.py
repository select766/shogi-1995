#!/usr/bin/env python3
"""Exercise the real guest transport and search lifecycle, without third-party packages."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import queue
import re
import subprocess
import threading
import time

ROOT = Path(__file__).resolve().parents[1]


def image_identity(image):
    digest = hashlib.sha256()
    with image.open('rb') as stream:
        while data := stream.read(1024 * 1024):
            digest.update(data)
    binary = subprocess.check_output(['debugfs', '-R', 'cat /shogi', str(image)], stderr=subprocess.DEVNULL)
    if not binary.startswith(b'\x7fELF'):
        raise ValueError('guest image lacks an ELF engine')
    return {'guest_image': str(image), 'image_sha256': digest.hexdigest(),
            'engine_sha256': hashlib.sha256(binary).hexdigest()}


def run(backend, timing_seconds, image=None, output=None):
    image = (image or ROOT / '.local/images/engine-root.ext2').resolve()
    report = {'backend': backend, 'started_at_utc': datetime.now(timezone.utc).isoformat(),
              **image_identity(image), 'test_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    if output is not None and output.exists():
        raise ValueError('preserve existing lifecycle evidence')
    results = output.with_suffix('.logs') if output is not None else ROOT / '.local/tests'
    if output is not None and results.exists():
        raise ValueError('preserve existing lifecycle logs')
    results.mkdir(parents=True, exist_ok=True)
    lines = []
    inbox = queue.Queue()
    err = (results / (backend + '-stderr.log')).open('w')
    process = subprocess.Popen([str(ROOT / 'run-shogi-1995.sh'), '--backend', backend, '--image', str(image)],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=err, text=True, bufsize=1)
    def reader():
        for line in process.stdout:
            line = line.rstrip('\n')
            lines.append(line)
            inbox.put(line)
        inbox.put(None)
    threading.Thread(target=reader, daemon=True).start()
    def send(line):
        process.stdin.write(line + '\n')
        process.stdin.flush()
    def wait(prefix, timeout=30):
        end = time.monotonic() + timeout
        while True:
            line = inbox.get(timeout=max(.001, end-time.monotonic()))
            if line is None:
                raise RuntimeError(f'engine exited waiting for {prefix}; see {err.name}')
            if line.startswith(prefix):
                return line
    try:
        start = time.monotonic()
        send('usi')
        wait('usiok', 150)
        report['startup_seconds'] = time.monotonic()-start
        assert any('option name MaxMovesToDraw type spin default 512 ' in s for s in lines)
        assert any('EnteringKingRule type combo default CSARule27 ' in s for s in lines)
        send('setoption name MaxMovesToDraw value 512')
        send('setoption name USI_OwnBook value false')
        send('isready')
        wait('readyok', 60)
        send('shogi1995stats')
        memory_line = wait('info string shogi1995 memory ')
        memory = {key:int(value) for key,value in re.findall(r'(total|free|swap)=(\d+)',memory_line)}
        assert 16*1024*1024 < memory['total'] <= 32*1024*1024
        assert memory['free'] > 0 and memory['swap'] == 0
        report['guest_memory_bytes'] = memory
        send('usinewgame')
        send('position startpos')
        send('go depth 2')
        move = wait('bestmove ', 30).split()[1]
        assert re.fullmatch(r'[1-9][a-i][1-9][a-i]\+?|[PLNSGBR]\*[1-9][a-i]', move), move
        report['first_move'] = move
        send('position startpos moves ' + move)
        send('go btime 180000 wtime 600000 binc 2000 winc 2000')
        time.sleep(.3)
        start = time.monotonic()
        send('stop')
        wait('bestmove ', 5)
        report['increment_search_stop_seconds'] = time.monotonic()-start
        # Exercise a maximum-length tournament move list through the UART.
        cycle = ['5i5h','5a5b','5h5i','5b5a']
        send('position startpos moves ' + ' '.join(cycle * 128))
        send('go depth 1')
        wait('bestmove ', 30)
        report['move_list_512_plies'] = True
        send('position startpos')
        start = time.monotonic()
        send('go btime 1000 wtime 1000 binc 2000 winc 2000')
        wait('bestmove ', 4)
        report['short_clock_seconds'] = time.monotonic()-start
        assert report['short_clock_seconds'] < 1.2
        send('position startpos')
        log_path = ROOT / '.local/run/usi.log'
        stops_before = log_path.read_text().count(' > stop\n')
        start = time.monotonic()
        send('go movetime 2000')
        wait('bestmove ', 5)
        report['movetime_2000_seconds'] = time.monotonic()-start
        assert 1.95 <= report['movetime_2000_seconds'] <= 2.3, report
        assert log_path.read_text().count(' > stop\n') == stops_before
        report['bridge_added_stop_during_movetime'] = False
        send('position startpos')
        timing_start = time.monotonic()
        first_timing_line = len(lines)
        send('go infinite')
        time.sleep(timing_seconds)
        start = time.monotonic()
        send('stop')
        wait('bestmove ', 5)
        report['infinite_stop_seconds'] = time.monotonic()-start
        if timing_seconds >= 5:
            elapsed = time.monotonic()-timing_start
            samples = [int(m.group(1)) for line in lines[first_timing_line:]
                       if (m := re.search(r'\btime (\d+)\b', line))]
            assert samples, 'no guest timing information'
            report['host_search_seconds'] = elapsed
            report['guest_last_info_seconds'] = max(samples)/1000
            report['guest_host_clock_ratio'] = max(samples)/1000/elapsed
            assert .98 <= report['guest_host_clock_ratio'] <= 1.02, report
        send('quit')
        assert process.wait(timeout=10) == 0
        report['passed'] = True
        print(json.dumps(report, ensure_ascii=False))
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        err.close()
        report['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        target = output if output is not None else results / (backend + '.json')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2) + '\n')
        (results / (backend + '-stdout.log')).write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--backend', choices=('86box','qemu'), default='86box')
    parser.add_argument('--timing-seconds', type=float, default=.3)
    parser.add_argument('--image', type=Path, help='Frozen candidate image; otherwise the actual default image')
    parser.add_argument('--output', type=Path, help='Preserve lifecycle evidence at a new path')
    args = parser.parse_args()
    run(args.backend, args.timing_seconds, args.image, args.output)
