#!/usr/bin/env python3
"""Record actual compiler and input identities after a successful build."""
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


modern_version = subprocess.check_output(['gcc', '-dumpfullversion'], text=True).strip()
modern_description = subprocess.check_output(['gcc', '--version'], text=True).splitlines()[0]
inputs = ['assets.json', 'compatibility.patch', 'relay.c', 'prepare.py', 'setup.sh',
          'build-modern-objects.sh', 'guest-build.sh', 'guest-build.py', 'write-manifests.py']
for variant, name in [('old', 'gnushogi-gcc270'), ('modern', 'gnushogi-gcc1140')]:
    record = {
        'engine_id': 'gnushogi-1.2p03-' + variant,
        'engine_sha256': sha(HERE / 'bin' / name),
        'image_sha256': sha(HERE / 'guest.ext2'),
        'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'source_worktree_dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip()),
        'source_archive_url': 'https://ftp.gnu.org/gnu/gnushogi/gnushogi-1.2p03.tar.gz',
        'source_archive_sha256': sha(HERE / 'vendor/gnushogi-1.2p03.tar.gz'),
        'compiler': 'GCC 2.7.0' if variant == 'old' else 'GCC ' + modern_version,
        'host_gcc': modern_description,
        'flags': '-O2 -funroll-loops -m486' if variant == 'old' else
                 '-O2 -funroll-loops -m32 -march=i486 -mtune=i486 -std=gnu89 -fcommon -fgnu89-inline -fno-pie -fno-stack-protector',
        'runtime': 'Linux 1.2.13 / libc 5.0.9; GCC 2.7.0 driver and 1995 binutils link both variants',
        'adapter_sha256': sha(HERE / 'usi.py'),
        'relay_source_sha256': sha(HERE / 'relay.c'),
        'guest_kernel_sha256': sha(HERE / 'guest-vmlinuz'),
        'build_inputs_sha256': {name: sha(HERE / name) for name in inputs},
        'guest_init_source_sha256': sha(ROOT / 'src/compat/guest-init.c'),
        'notes': [
            'GNU comparator only; no research engine replacement',
            'fixed historical table sizes; USI_Hash=2 does not allocate exactly 2MiB',
            'no opening book or pondering; time poll every 1000 nodes, minimum depth permits overruns',
            'VM filesystem timestamps differ across builds; image is hash-identified, not claimed bit-reproducible',
            'gnushogi-gcc1140 is the compatibility filename; actual modern compiler version is recorded above',
        ],
    }
    (HERE / ('manifest-' + variant + '.json')).write_text(json.dumps(record, indent=2) + '\n')
