#!/usr/bin/env python3
"""Check ELF form and obvious post-Pentium instructions in the final image."""
import json
import hashlib
from pathlib import Path
import re
import subprocess

root=Path(__file__).resolve().parents[1]
binary=root/'.local/guest-root/shogi'
header=subprocess.check_output(['readelf','-h',str(binary)],text=True)
segments=subprocess.check_output(['readelf','-l',str(binary)],text=True)
assert 'ELF32' in header and re.search(r'Type:\s+EXEC',header)
assert 'INTERP' not in segments and 'DYNAMIC' not in segments
assembly=subprocess.check_output(['objdump','-d',str(binary)],text=True)
pattern=r'\b(cmov\w*|fcmov\w*|popcnt\w*|rdrand|rdseed|xgetbv|rdtscp|pext|pdep|lzcnt|tzcnt|prefetch\w*)\b|%[xyz]mm\d|%mm[0-7]\b'
bad=[line for line in assembly.splitlines() if re.search(pattern,line)]
report={'engine_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),
        'elf32_static_exec':True,'later_instruction_candidates':bad,
        'note':'Known-opcode screening plus real Pentium guest execution; not a complete ISA proof.'}
out=root/'.local/tests';out.mkdir(exist_ok=True)
(out/'target.json').write_text(json.dumps(report,indent=2)+'\n')
assert not bad, '\n'.join(bad[:20])
print('ELF32 static EXEC; no screened post-Pentium instructions')
