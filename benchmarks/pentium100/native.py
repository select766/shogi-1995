#!/usr/bin/env python3
"""Run the exact 86Box Dhrystone executable on the host with a monotonic clock."""
import hashlib
import json
import re
import statistics
import subprocess
import time
from pathlib import Path

root = Path(__file__).resolve().parents[2]
exe = root / '.local/pentium100-dhry/dhry'
expected_hash = 'e8a78d7973290299054597bb4baf3df86ab72cef464e6fb4300e9ae445e3f89c'
actual_hash = hashlib.sha256(exe.read_bytes()).hexdigest()
if actual_hash != expected_hash:
    raise SystemExit('Executable differs from the 86Box measurement: ' + actual_hash)
runs = 500_000_000
samples = []
for i in range(3):
    start = time.monotonic()
    proc = subprocess.run([str(exe)], input=f'{runs}\n', text=True, capture_output=True, check=True)
    elapsed = time.monotonic() - start
    out = proc.stdout
    for name, expected in [('Int_Glob','5'), ('Bool_Glob','1'), ('Ch_1_Glob','A'), ('Ch_2_Glob','B'), ('Arr_1_Glob[8]','7'), ('Arr_2_Glob[8][7]',str(runs+10)), ('Int_1_Loc','5'), ('Int_2_Loc','13'), ('Int_3_Loc','7'), ('Enum_Loc','1')]:
        match = re.search(r'^'+re.escape(name)+r':\s*(\S+)', out, re.M)
        if not match or match.group(1) != expected:
            raise SystemExit('Unexpected benchmark output: '+name)
    match = re.search(r'Dhrystones per Second:\s+([0-9.]+)', out)
    if not match:
        raise SystemExit('Missing benchmark result')
    samples.append({'sample':i+1, 'wall_seconds':elapsed, 'host_wall_dhrystones_per_second':runs/elapsed, 'guest_program_dhrystones_per_second':float(match.group(1)), 'stdout':out})
    print('sample', i+1, 'wall seconds', round(elapsed, 6), 'Dhrystones/s', round(runs/elapsed, 1), flush=True)
result = {'binary_sha256':actual_hash, 'iterations_per_sample':runs, 'clock':'host time.monotonic, whole process including startup and output', 'samples':samples, 'median_host_wall_dhrystones_per_second':statistics.median(s['host_wall_dhrystones_per_second'] for s in samples)}
outfile = root / 'results/2026-11-12/dhrystone-native.json'
outfile.write_text(json.dumps(result, indent=2)+'\n')
print('saved', outfile, flush=True)
