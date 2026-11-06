import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pair_nodes', ROOT / 'scripts/evaluate-pair.py')
pair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pair)


class PairNodeTests(unittest.TestCase):
    def run_fixture(self, folder, nodes, wrong_nodes=False):
        dataset = folder / 'data.jsonl'
        records = [{'id': str(i), 'sfen': 'fixture', 'bestmove': 'fixture'} for i in range(4)]
        dataset.write_text(''.join(json.dumps(r) + '\n' for r in records))
        paths = []
        for key in ['baseline', 'candidate']:
            path = folder / (key + '.json')
            path.write_text(json.dumps({'id': key, 'command': ['fixture-engine'], 'engine_sha256': key}))
            paths.append(path)
        calls = []

        def fake_run(command, **kwargs):
            if Path(command[1]).name != 'evaluate-accuracy.py':
                return
            value = lambda flag: command[command.index(flag) + 1]
            start, count = int(value('--offset')), int(value('--limit'))
            limit = int(value('--nodes')) if '--nodes' in command else None
            calls.append((value('--engine-id'), limit))
            rows = records[start:start + count]
            result = dict(complete=True, dataset_sha256=pair.digest(dataset), sample_ids=[r['id'] for r in rows],
                          engine_sha256=value('--engine-sha256'), engine_id=value('--engine-id'),
                          engine_command=json.loads(value('--engine-command')), model_options={},
                          milliseconds=int(value('--milliseconds')), nodes=129 if wrong_nodes else limit,
                          mode='fixed_nodes' if limit is not None else 'fixed_byoyomi',
                          details=[{'id': r['id'], 'match': True} for r in rows], elapsed_seconds=1)
            Path(value('--output')).write_text(json.dumps(result))

        argv = ['evaluate-pair.py', '--baseline', str(paths[0]), '--candidate', str(paths[1]),
                '--dataset', str(dataset), '--output', str(folder / 'out'), '--block-size', '2']
        if nodes is not None:
            argv += ['--nodes', str(nodes)]
        with patch.object(sys, 'argv', argv), patch.object(pair.subprocess, 'run', side_effect=fake_run):
            pair.main()
        return calls

    def test_fixed_nodes_reaches_each_engine_in_alternating_order_and_is_frozen(self):
        with tempfile.TemporaryDirectory() as name:
            folder = Path(name)
            calls = self.run_fixture(folder, 128)
            self.assertEqual(calls, [('baseline', 128), ('candidate', 128), ('candidate', 128), ('baseline', 128)])
            result = json.loads((folder / 'out/candidate.json').read_text())
            self.assertTrue(result['complete'])
            self.assertEqual(result['nodes'], 128)
            self.assertEqual(result['mode'], 'fixed_nodes')
            with self.assertRaisesRegex(ValueError, 'resume identity differs'):
                self.run_fixture(folder, 256)

    def test_regular_time_mode_preserves_existing_resume_identity(self):
        with tempfile.TemporaryDirectory() as name:
            folder = Path(name)
            calls = self.run_fixture(folder, None)
            self.assertTrue(all(limit is None for _, limit in calls))
            self.assertNotIn('nodes', json.loads((folder / 'out/identity.json').read_text()))

    def test_changed_node_limit_in_a_block_is_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            with self.assertRaisesRegex(ValueError, 'block identity mismatch'):
                self.run_fixture(Path(name), 128, wrong_nodes=True)


if __name__ == '__main__':
    unittest.main()
