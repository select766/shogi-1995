"""Prevent training before prerequisite exit or after a failed/changed job."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('after_job', ROOT / 'scripts/run-after-job.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class JobTests(unittest.TestCase):
    def setUp(self):
        self.expected = {'pid': 123, 'plan_sha256': 'plan', 'process_start_time': '100'}
        self.state = {'pid': 123, 'plan_sha256': 'plan', 'status': 'executing'}

    def test_running_job_waits(self):
        self.assertFalse(module.job_ready(self.expected, self.state, ('S', '100')))

    def test_complete_still_waits_for_exit(self):
        self.state['status'] = 'complete'
        self.assertFalse(module.job_ready(self.expected, self.state, ('R', '100')))
        self.assertTrue(module.job_ready(self.expected, self.state, ('Z', '100')))
        self.assertTrue(module.job_ready(self.expected, self.state, (None, None)))

    def test_failed_job_never_releases(self):
        self.state['status'] = 'stopped'
        with self.assertRaises(RuntimeError):
            module.job_ready(self.expected, self.state, ('S', '100'))

    def test_reused_or_missing_pid_does_not_certify_completion(self):
        for identity in [('S', '101'), (None, None)]:
            with self.subTest(identity=identity), self.assertRaises(RuntimeError):
                module.job_ready(self.expected, self.state, identity)

    def test_changed_plan_or_pid_rejected(self):
        for key in ['pid', 'plan_sha256']:
            with self.subTest(key=key), self.assertRaises(ValueError):
                module.job_ready(self.expected, dict(self.state, **{key: 'changed'}), ('S', '100'))

    def test_input_manifest_completion_and_validation_binding(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'manifest.json'
            path.write_text(json.dumps({'complete': True, 'records': 100, 'validation_sha256': 'fixed'}))
            requirements = {str(path): {'fields': {'complete': True, 'validation_sha256': 'fixed'}}}
            snapshots = module.completed_inputs(requirements)
            self.assertEqual(snapshots[str(path)]['records'], 100)
            for value in [{'complete': False, 'validation_sha256': 'fixed'},
                          {'complete': True, 'validation_sha256': 'other'}]:
                path.write_text(json.dumps(value))
                with self.assertRaises(ValueError):
                    module.completed_inputs(requirements)

    def test_changed_frozen_input_rejected_even_with_matching_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'manifest.json'
            path.write_text('{"complete":true}')
            requirements = {str(path): {'sha256': module.digest(path), 'fields': {'complete': True}}}
            path.write_text('{"complete":true,"changed":true}')
            with self.assertRaises(ValueError):
                module.completed_inputs(requirements)

    def test_real_process_must_exit_before_planned_step_executes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            parent = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
            worker = None
            try:
                parent_state = root / 'parent.json'
                marker = root / 'executed'
                parent_state.write_text(json.dumps({'status': 'complete', 'pid': parent.pid, 'plan_sha256': 'fixed'}))
                plan = {'prerequisite_job': {'state': str(parent_state), 'pid': parent.pid,
                         'process_start_time': module.process_identity(parent.pid)[1], 'plan_sha256': 'fixed'},
                        'code_sha256': {}, 'steps': [{'description': 'write marker', 'log': str(root / 'step.log'),
                         'argv': [sys.executable, '-c', 'from pathlib import Path; import sys; Path(sys.argv[1]).write_text("done")', str(marker)]}]}
                path = root / 'plan.json'
                path.write_text(json.dumps(plan))
                state_path = root / 'state.json'
                worker = subprocess.Popen([sys.executable, str(ROOT / 'scripts/run-after-job.py'),
                                           '--plan', str(path), '--state', str(state_path)],
                                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                deadline = time.monotonic() + 5
                while not state_path.exists() and time.monotonic() < deadline:
                    time.sleep(.01)
                self.assertTrue(state_path.exists())
                time.sleep(.2)
                self.assertFalse(marker.exists())
                parent.terminate()
                parent.wait(5)
                stdout, stderr = worker.communicate(timeout=8)
                self.assertEqual(worker.returncode, 0, stderr)
                self.assertEqual(marker.read_text(), 'done')
                self.assertEqual(json.loads(state_path.read_text())['status'], 'complete')
                repeated = subprocess.run([sys.executable, str(ROOT / 'scripts/run-after-job.py'),
                                           '--plan', str(path), '--state', str(state_path)], capture_output=True)
                self.assertNotEqual(repeated.returncode, 0)
                self.assertEqual(marker.read_text(), 'done')
            finally:
                if parent.poll() is None:
                    parent.terminate()
                    parent.wait(5)
                if worker is not None and worker.poll() is None:
                    worker.terminate()
                    worker.communicate(timeout=5)


if __name__ == '__main__':
    unittest.main()
