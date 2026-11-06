"""Package actual frozen runtimes without changing their binary or staging area."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('frozen_package', ROOT / 'scripts/package-frozen-runtime.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = ROOT / 'manifests/halfkp-nnue-w8-h0-width-kernel-v1-candidate.json'
        self.model = ROOT / '.local/profiles/halfkp-nnue-w16-h8-width-kernel-v1/model.bin'
        if not self.manifest.exists() or not self.model.exists():
            self.skipTest('requires the locally qualified frozen HalfKP runtimes')
        self.source = json.loads(self.manifest.read_text())
        self.output = self.root / 'profile'

    def changed(self, **fields):
        path = self.root / 'changed.json'
        path.write_text(json.dumps(dict(self.source, **fields)))
        return path

    def package(self, path=None):
        return module.package(path or self.manifest, self.model, self.output, 'test-profile',
                              'Functional packaging verification, not a strength candidate')

    def test_both_frozen_runtimes_keep_binary_config_source_and_original_files(self):
        staging = ROOT / '.local/guest-root/shogi'
        staging_before = module.digest(staging)
        for runtime in ['output32', 'width-kernel']:
            with self.subTest(runtime=runtime):
                self.manifest = ROOT / f'manifests/halfkp-nnue-w8-h0-{runtime}-v1-candidate.json'
                self.source = json.loads(self.manifest.read_text())
                self.output = self.root / runtime
                original = Path(self.source['command'][2])
                result = self.package()
                self.assertEqual(result['engine_sha256'], self.source['engine_sha256'])
                self.assertEqual(result['source_commit'], self.source['source_commit'])
                self.assertEqual(result['source_tree_sha256'], self.source['source_tree_sha256'])
                self.assertEqual(result['model_sha256'], module.digest(self.model))
                self.assertEqual(module.digest(original), self.source['image_sha256'])
                self.assertEqual(module.digest(self.output / 'shogi'), result['engine_sha256'])
                self.assertEqual(module.digest(self.output / 'root.ext2'), result['image_sha256'])
                self.assertNotEqual(result['model_sha256'], self.source['model_sha256'])
                with self.assertRaises(FileExistsError):
                    self.package()
        self.assertEqual(module.digest(staging), staging_before)

    def test_changed_image_hash_rejected(self):
        with self.assertRaisesRegex(ValueError, 'image hash differs'):
            self.package(self.changed(image_sha256='wrong'))
        self.assertFalse(self.output.exists())

    def test_changed_binary_hash_rejected(self):
        with self.assertRaisesRegex(ValueError, 'contents differ'):
            self.package(self.changed(engine_sha256='wrong'))

    def test_changed_source_binding_rejected(self):
        with self.assertRaisesRegex(ValueError, 'source commit binding'):
            self.package(self.changed(source_tree_sha256='wrong'))

    def test_uncommitted_runtime_source_rejected(self):
        with self.assertRaisesRegex(ValueError, 'committed source required'):
            self.package(self.changed(source_worktree_dirty=True))

    def test_untrusted_guest_path_rejected(self):
        with self.assertRaisesRegex(ValueError, 'guest model path'):
            self.package(self.changed(configured_guest_options={'EvalFile': '/eval/../model.bin'},
                                      engine_options={'EvalFile': '/eval/../model.bin'}))


if __name__ == '__main__':
    unittest.main()
