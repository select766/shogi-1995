#!/usr/bin/env python3
"""Qualify a freshly committed/built runtime after the ordinary trial exits."""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / '.local/venv/bin/python'
sys.path.insert(0, str(ROOT / 'src'))
from shogi1995.provenance import source_identity


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--work', required=True, type=Path)
    p.add_argument('--results', required=True, type=Path)
    args = p.parse_args()
    prerequisite_path = ROOT / '.local/jobs/halfkp-fixed-model-counter-ordinary-v1.json'
    prerequisite = json.loads(prerequisite_path.read_text())
    if (prerequisite['pid'] != 769485
            or prerequisite['plan_sha256'] != 'e56a02aca6f76e8074dda6d17c2749fa6d23eb9af312b9a274c342eb7f39cb1e'
            or prerequisite['status'] != 'complete' or prerequisite.get('child_pid') is not None):
        raise ValueError('full ordinary trial must complete before radix qualification')
    try:
        fields = Path('/proc/769485/stat').read_text().split(') ', 1)[1].split()
    except FileNotFoundError:
        fields = None
    if fields and fields[0] != 'Z' and fields[19] == '9700121':
        raise ValueError('ordinary trial producer must exit before radix qualification')
    # Leave at least two hours for qualification, target speed and full1024.
    if datetime.now(timezone.utc) >= datetime(2026, 11, 7, 4, 0, tzinfo=timezone.utc):
        raise ValueError('insufficient exploration window before06UTC')
    if args.work.exists():
        raise ValueError('preserve previous attempt; choose a new work directory')
    identity = source_identity()
    build = json.loads((ROOT / '.local/last-engine-build.json').read_text())
    binary = ROOT / '.local/guest-root/shogi'
    if (identity['source_worktree_dirty'] or build['source_worktree_dirty']
            or build['source_tree_sha256'] != identity['source_tree_sha256']
            or build['engine_sha256'] != sha(binary)):
        raise ValueError('commit and rebuild the current radix source before qualification')
    if subprocess.check_output(['nvidia-smi', '--query-compute-apps=pid',
                                '--format=csv,noheader,nounits'], text=True).strip():
        raise ValueError('GPU compute job is active')
    with (ROOT / '.local/run/engine.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    model = ROOT / '.local/frozen-models/halfkp-20261107-1000/model.bin'
    model_sha = 'd42b68f3da24fe3d77d9549aeca1c0b6a4ced375d7ff7fa6b14c737d876bdeff'
    assert sha(model) == model_sha
    old_ref = ROOT / '.local/validation/halfkp-single-thread-counter-v1/native-reference.json'
    assert sha(old_ref) == '96f621bba0f44328450eeec738ab688e82c0f346170aa6f84cb56f21a0b117d6'
    old = json.loads(old_ref.read_text())
    assert old['complete'] and old['model_sha256'] == model_sha and len(old['details']) == 256
    assert old['mode'] == 'fixed_nodes' and old['nodes'] == 10000 and old['backend'] == 'native'
    name = 'halfkp-fixed-w8-h0-128m-radix-v1'
    profile = ROOT / '.local/profiles' / name
    frozen = ROOT / 'manifests' / (name + '-candidate.json')
    if profile.exists() or frozen.exists() or (ROOT / '.local/candidates' / name).exists():
        raise ValueError('preserve existing candidate')
    args.work.mkdir(parents=True)
    args.results.mkdir(parents=True, exist_ok=True)
    report_path = args.results / 'halfkp-fixed-model-radix-qualification-v1.json'
    if report_path.exists():
        raise ValueError('preserve existing report')
    state_path = args.work / 'state.json'
    state = {'status': 'executing', 'pid': os.getpid(), 'started_at_utc': now(),
             'source_identity': identity, 'build': build, 'steps': []}
    artifacts = {}

    def save():
        temporary = state_path.with_suffix('.partial')
        temporary.write_text(json.dumps(state, indent=2) + '\n')
        temporary.replace(state_path)

    def run(label, argv, result=None, stdout_json=False):
        state.update(current_step=label, current_argv=[str(x) for x in argv])
        save()
        log = args.work / (label + '.log')
        with log.open('x') as stream:
            subprocess.run([str(x) for x in argv], cwd=ROOT, stdout=stream,
                           stderr=subprocess.STDOUT, check=True)
        if stdout_json:
            value = json.loads(log.read_text())
            with result.open('x') as stream:
                json.dump(value, stream, indent=2)
                stream.write('\n')
        if result is not None:
            value = json.loads(result.read_text())
            if value.get('passed') is False:
                raise ValueError('failed result: ' + str(result))
            artifacts[str(result)] = sha(result)
        state['steps'].append({'label': label, 'log': str(log), 'log_sha256': sha(log),
                               'finished_at_utc': now()})
        save()

    def test(label, script, arguments):
        result = args.results / (label + '.json')
        run(label, [PYTHON, ROOT / 'tests' / script, *arguments, '--output', result], result)
        return json.loads(result.read_text())

    data = Path('/media/select766/HDCZ-UT/s7ubuntu/dev/shogi-1995/training/halfkp-qsearch-v1/raw-validation/shuffled/shuffled.bin')
    quick = Path('/media/select766/HDCZ-UT/s7ubuntu/dev/shogi-1995/evaluation/floodgate-hcpe-1995-v1/quick.jsonl')
    try:
        save()
        header = subprocess.check_output(['readelf', '-h', str(binary)], text=True)
        segments = subprocess.check_output(['readelf', '-l', str(binary)], text=True)
        assert 'ELF32' in header and 'Intel 80386' in header and 'EXEC (Executable file)' in header and 'INTERP' not in segments
        assembly = subprocess.check_output(['objdump', '-d', '--no-show-raw-insn', str(binary)], text=True)
        forbidden = re.compile(r'(?:cmov\w*|fcmov\w*|fcomip?|fucomip?|rdrand|rdseed|rdpmc|sysenter|syscall|prefetch\w*|ldmxcsr|stmxcsr|fxsave\w*|fxrstor\w*|xsave\w*|xrstor\w*|fisttp\w*|popcnt\w*|lzcnt\w*|tzcnt\w*|emms|[sml]fence|clflush\w*|xgetbv|xsetbv|vzeroupper|vzeroall)', re.I)
        hits = []
        for line in assembly.splitlines():
            if not re.match(r'^\s*[0-9a-f]+:', line):
                continue
            instruction = line.split(':', 1)[1].split('#', 1)[0].strip()
            if instruction and (forbidden.fullmatch(instruction.split()[0])
                                or re.search(r'%(?:[xyz]mm\d+|mm[0-7])\b', instruction, re.I)):
                hits.append(line)
        assert not hits, hits[:8]
        (args.work / 'target-readelf.log').write_text(header + segments)
        (args.work / 'target-objdump.log').write_text(assembly)
        unit = args.work / 'fixed-radix-head-ubsan'
        run('compile-unit', ['g++', '-std=c++17', '-O2', '-fsanitize=undefined',
                            '-fno-sanitize-recover=undefined', '-I' + str(ROOT / 'vendor/YaneuraOu/source'),
                            ROOT / 'tests/fixed_radix_head.cpp', '-o', unit])
        unit_result = args.results / 'halfkp-fixed-radix-head-ubsan-v1.json'
        run('unit', [unit, model], unit_result, True)
        assert json.loads(unit_result.read_text())['cases'] == 145196
        run('package', [PYTHON, ROOT / 'scripts/package-candidate.py', '--name', name, '--model', model,
                        '--feature-difference', '固定D42モデル。packed加算値と単一スレッド用全幅uint64を維持し、同一出力積和をradix256残差と共通項で計算。重み・丸めは不変。速度・棋力は未測定'])
        run('profile', [PYTHON, ROOT / 'scripts/prepare-usi-profile.py', '--manifest',
                        ROOT / '.local/candidates' / name / 'manifest.json', '--output', profile])
        shutil.copyfile(profile / 'manifest.json', frozen)
        manifest = json.loads(frozen.read_text())
        assert manifest['engine_sha256'] == sha(binary) and manifest['model_sha256'] == model_sha
        artifacts[str(frozen)] = sha(frozen)
        value_result = args.results / 'halfkp-fixed-radix-values-v1.json'
        run('values', [PYTHON, ROOT / 'tests/tiny_parity.py', '--model', model, '--data', data,
                       '--count', 512, '--binary', profile / 'shogi', '--log-prefix', args.work / 'values.logs'],
            value_result, True)
        test('halfkp-fixed-radix-native-lifecycle-v1', 'fixed_radix_lifecycle.py',
             ['--model', model, '--data', data, '--binary', profile / 'shogi', '--work', args.work / 'native-lifecycle'])
        checked = test('halfkp-fixed-radix-native-search-v1', 'tiny_incremental.py',
                       ['--model', model, '--binary', profile / 'shogi', '--reference', old_ref,
                        '--expected-kernel-width', 8, '--expected-fc-packed', 0, '--expected-fc-bits', 0,
                        '--expected-accumulator-packed', 1, '--expected-accumulator-bits', 16])
        assert checked['positions'] == 256 and checked['counters']['head_radix'] == 1
        assert checked['counters']['head_verified'] > 1000
        # Guest search parity requires a reference generated by the NEW binary.
        native = args.work / 'native-reference.json'
        run('native-reference', [PYTHON, ROOT / 'scripts/evaluate-accuracy.py', '--dataset', quick,
                                '--output', native, '--engine-command', json.dumps([str(profile / 'shogi')]),
                                '--engine-id', name + '-native', '--engine-sha256', manifest['engine_sha256'],
                                '--engine-options', json.dumps({'EvalFile': str(profile / 'model.bin')}),
                                '--engine-manifest', frozen, '--backend', 'native', '--nodes', 10000,
                                '--search-diagnostics'], native)
        new = json.loads(native.read_text())
        assert new['complete'] and len(new['details']) == 256
        assert not any(new[k] for k in ('errors', 'illegal_moves', 'time_overruns'))
        for a, b in zip(old['details'], new['details']):
            for field in ('id', 'sfen', 'actual', 'final_nodes', 'completed_depth'):
                assert a[field] == b[field], (field, a, b)
        guest = test('halfkp-fixed-radix-guest-values-v1', 'guest_auto_model.py',
                     ['--profile', profile, '--data', data])
        test('halfkp-fixed-radix-guest-nodes-v1', 'guest_nodes_parity.py',
             ['--manifest', frozen, '--reference', native, '--count', 8, '--automatic-model',
              '--expected-output-bits', 32, '--expected-kernel-width', 8, '--expected-fc-packed', 0,
              '--expected-fc-bits', 0, '--expected-accumulator-packed', 1, '--expected-accumulator-bits', 16])
        test('halfkp-fixed-radix-guest-lifecycle-v1', 'fixed_radix_lifecycle.py',
             ['--model', model, '--data', data, '--guest-manifest', frozen, '--work', args.work / 'guest-lifecycle'])
        test('halfkp-fixed-radix-usi-lifecycle-v1', 'usi_smoke.py', ['--image', profile / 'root.ext2'])
        report = {'complete': True, 'passed': True, 'verified_at_utc': now(), 'profile': str(frozen),
                  'source_identity': identity, 'build': build, 'engine_sha256': manifest['engine_sha256'],
                  'image_sha256': manifest['image_sha256'], 'model_sha256': model_sha,
                  'native_values': 512, 'native_search_positions': 256,
                  'verified_heads': checked['counters']['head_verified'], 'guest_memory': guest['guest_memory'],
                  'elf32_static_x86': True, 'known_post_pentium_opcode_hits': hits,
                  'artifacts': artifacts, 'driver_sha256': sha(Path(__file__)),
                  'scope': 'correctness, real guest operation and RAM only; speed and ordinary strength unmeasured'}
        with report_path.open('x') as stream:
            json.dump(report, stream, indent=2)
            stream.write('\n')
        state.update(status='complete', report=str(report_path), report_sha256=sha(report_path))
    except BaseException as error:
        state.update(status='stopped', error=repr(error))
        raise
    finally:
        state['finished_at_utc'] = now()
        save()


if __name__ == '__main__':
    main()
