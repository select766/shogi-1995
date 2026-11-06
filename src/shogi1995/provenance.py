"""Stable source and machine identities for reproducible measurement records."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path('vendor/YaneuraOu/source')


def source_tree_hash(commit=None):
    h = hashlib.sha256()
    if commit:
        data = subprocess.check_output(['git','archive',commit,str(SOURCE)], cwd=ROOT)
        with tarfile.open(fileobj=io.BytesIO(data)) as archive:
            for entry in sorted((m for m in archive.getmembers() if m.isfile()),key=lambda m:Path(m.name)):
                h.update(entry.name.encode()+hashlib.sha256(archive.extractfile(entry).read()).digest())
    else:
        for file in sorted((ROOT/SOURCE).rglob('*')):
            if file.is_file():
                h.update(str(file.relative_to(ROOT)).encode()+hashlib.sha256(file.read_bytes()).digest())
    return h.hexdigest()


def source_identity():
    commit = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    current = source_tree_hash()
    dirty = current != source_tree_hash(commit)
    return {'source_commit':commit,'source_tree_sha256':current,'source_worktree_dirty':dirty,
            'source_commit_binding':'HEAD_plus_uncommitted_source_tree' if dirty else 'committed_source_tree'}


def environment_identity(backend):
    paths = ['manifests/assets.json']
    if backend == '86box':
        paths.append('config/86box/pentium100.cfg.in')
    files = {name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in paths}
    if backend == 'native':
        files['host_cpu'] = next((line.split(':',1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')), 'unknown')
    signature = hashlib.sha256(json.dumps({'backend':backend,**files},sort_keys=True).encode()).hexdigest()
    return {'signature':signature,'components':files}
