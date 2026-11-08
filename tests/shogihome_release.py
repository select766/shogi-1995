#!/usr/bin/env python3
"""Verify the assembled launcher, optional book, NNUE and configurable USI settings."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from shogi1995.usi import Engine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    profile = args.profile.resolve()
    output = args.output.resolve()
    if output.exists():
        raise ValueError('preserve existing results')
    manifest = json.loads((profile / 'manifest.json').read_text())
    started = datetime.now(timezone.utc).isoformat()
    logs = ROOT / '.local/tests' / output.stem
    with Engine([str(profile / 'run.sh')], '/tmp', logs) as engine:
        assert engine.name == manifest['usi_name']
        def value(key):
            engine.send('getoption ' + key)
            _, lines = engine.until('Options[' + key + ']', 10)
            return lines[-1].split('=', 1)[1].strip()
        for key, expected in manifest['configured_guest_options'].items():
            assert value(key) == expected, (key, value(key), expected)
        engine.send('shogi1995stats')
        _, lines = engine.until('info string shogi1995 memory ', 10)
        memory = {k: int(v) for k, v in re.findall(r'(total|free|swap)=(\d+)', lines[-1])}
        assert memory['swap'] == 0 and 0 < memory['free'] < memory['total'] <= 32 * 1024 * 1024
        result = engine.search_position('position startpos', 'go depth 1', 30)
        assert re.fullmatch(r'[1-9][a-i][1-9][a-i]\+?|[PLNSGBR]\*[1-9][a-i]', result['actual'])
        if manifest['private_book_included']:
            # Book outputs stay under ignored .local/: publish only whether it hit.
            trace = (logs / 'protocol.log').read_text()
            assert 'book file fallback' in trace and re.search(r'\bnodes 0\b.*\bpv ', trace)
        engine.send('setoption name USI_OwnBook value false')
        engine.send('setoption name BookFile value no_book')
        engine.send('setoption name NetworkDelay value 0')
        engine.send('setoption name NetworkDelay2 value 0')
        engine.reset()
        assert value('USI_OwnBook') == 'false' and value('BookFile') == 'no_book'
        assert value('NetworkDelay') == '0' and value('NetworkDelay2') == '0'
        assert value('EvalFile') == '/eval/model.bin'
        timed = engine.search_position('position startpos', 'go movetime 2000', 6)
        assert 1950 <= timed['host_ms'] <= 2300, timed
        engine.send('position startpos')
        engine.send('go btime 180000 wtime 600000 binc 2000 winc 2000')
        time.sleep(.3)
        before = time.monotonic()
        engine.send('stop')
        engine.until('bestmove ', 5)
        stop_seconds = time.monotonic() - before
        engine.send('position startpos moves ' + ' '.join(['5i5h', '5a5b', '5h5i', '5b5a'] * 128))
        engine.send('go depth 1')
        engine.until('bestmove ', 30)
        engine.send('shogi1995evalstats')
        engine.until('info string shogi1995 accumulators ', 10)
        trace = (logs / 'protocol.log').read_text()
        assert 'tiny network loaded: /eval/model.bin' in trace
        assert 'head_radix=1' in trace
    assert engine.process.returncode == 0
    # Repeated process startup checks the exact same launcher from another cwd.
    with Engine([str(profile / 'run.sh')], '/tmp', logs / 'restart') as again:
        again.send('shogi1995stats')
        again.until('info string shogi1995 memory ', 10)
    assert again.process.returncode == 0
    report = {'passed': True, 'started_at_utc': started,
              'finished_at_utc': datetime.now(timezone.utc).isoformat(),
              'image_sha256': manifest['image_sha256'], 'payload_sha256': manifest['payload_sha256'],
              'book_included': manifest['private_book_included'],
              'book_hit_confirmed': manifest['private_book_included'],
              'first_response_ms': result['host_ms'], 'movetime_2000_ms': timed['host_ms'],
              'guest_memory': memory, 'ordinary_tournament_go_stop_seconds': stop_seconds,
              'move_list_512_plies': True, 'nnue_and_radix_loaded': True,
              'book_and_network_delays_configurable': True, 'restart_from_other_cwd_passed': True,
              'scope': '86Box launcher/USI operation; not a ShogiHome GUI test or a strength measurement'}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
