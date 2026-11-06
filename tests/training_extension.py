#!/usr/bin/env python3
"""Reject integrity and held-out-set drift before a larger training run."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('extension', ROOT/'scripts/verify-training-extension.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ExtensionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        identity = dict(series='tanuki-original-blocks-v2', seed=20261106,
                        move_codec='PSV', source='approved-originals', source_readme_sha256='readme',
                        exclusions_sha256='excluded', block_size=4096, validation_files=['heldout'],
                        training_file_count=984, extractor_sha256='extractor', complete=True)
        self.a, self.b = copy.deepcopy(identity), copy.deepcopy(identity)
        val_block = dict(split='validation', file='heldout', offset=0, sha256='v')
        train_block = dict(split='train', file='training', offset=0, sha256='t')
        self.a['blocks'] = [val_block, train_block]
        self.b['blocks'] = [val_block, train_block, dict(split='train', file='training', offset=4096, sha256='t2')]
        for name, manifest, train in [('a', self.a, b'a'*80), ('b', self.b, b'a'*80+b'b'*80)]:
            manifest['outputs'] = {}
            for split, data in [('validation', b'v'*40), ('train', train)]:
                path = self.root/f'{name}-{split}.bin'
                path.write_bytes(data)
                manifest['outputs'][split] = dict(file=str(path), records=len(data)//40, sha256=module.digest(path))

    def verify(self):
        paths = []
        for name, manifest in [('a', self.a), ('b', self.b)]:
            path = self.root/f'{name}.json'
            path.write_text(json.dumps(manifest))
            paths.append(path)
        return module.verify(*paths, 4)

    def test_extension_preserves_validation_and_old_samples(self):
        report = self.verify()
        self.assertTrue(report['passed'])
        self.assertEqual((report['reference_records'], report['extended_records']), (2, 4))

    def test_recomputed_hash_cannot_hide_replaced_old_training_samples(self):
        row = self.b['outputs']['train']
        Path(row['file']).write_bytes(b'c'*160)
        row['sha256'] = module.digest(row['file'])
        with self.assertRaisesRegex(ValueError, 'original prefix'):
            self.verify()

    def test_recomputed_hash_cannot_hide_changed_validation(self):
        row = self.b['outputs']['validation']
        Path(row['file']).write_bytes(b'z'*40)
        row['sha256'] = module.digest(row['file'])
        with self.assertRaisesRegex(ValueError, 'held-out validation'):
            self.verify()

    def test_corrupt_bytes_rejected(self):
        Path(self.b['outputs']['train']['file']).write_bytes(b'x'*160)
        with self.assertRaisesRegex(ValueError, 'raw bytes'):
            self.verify()

    def test_changed_validation_file_pool_rejected(self):
        self.b['validation_files'] = ['other']
        with self.assertRaisesRegex(ValueError, 'validation_files'):
            self.verify()

    def test_changed_source_blocks_rejected(self):
        self.b['blocks'] = copy.deepcopy(self.b['blocks'])
        self.b['blocks'][1]['offset'] = 99
        with self.assertRaisesRegex(ValueError, 'source block prefix'):
            self.verify()


if __name__ == '__main__':
    unittest.main()
