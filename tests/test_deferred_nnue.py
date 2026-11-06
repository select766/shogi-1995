from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile
import time
import unittest

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from shogi1995.provenance import source_tree_hash


class DeferredNNUEGateTests(unittest.TestCase):
    def fixture(self,folder,producer):
        pair=folder/'pair';pair.mkdir();(pair/'identity.json').write_text('{}')
        state,start=Path(f'/proc/{producer.pid}/stat').read_text().split(') ',1)[1].split()[0],Path(f'/proc/{producer.pid}/stat').read_text().split(') ',1)[1].split()[19]
        marker=folder/'ran';plan={'measurement_output':str(pair),'producer_pid':producer.pid,'producer_start_time':start,
            'measurement_identity_sha256':hashlib.sha256((pair/'identity.json').read_bytes()).hexdigest(),
            'dataset_sha256':'fixture','sample_ids':[str(i) for i in range(1024)],'source_tree_sha256':source_tree_hash(),'code_sha256':{},
            'steps':[{'description':'harmless fixture marker','log':str(folder/'step.log'),
                      'argv':[sys.executable,'-c','from pathlib import Path; Path('+repr(str(marker))+').write_text("ran")']}]}
        path=folder/'plan.json';path.write_text(json.dumps(plan));return pair,plan,path,marker

    def completed(self,pair,plan):
        report={'complete':True,'total':1024,'measured':1024,'dataset_sha256':'fixture','sample_ids':plan['sample_ids'],
                'backend':'86box','mode':'fixed_byoyomi','milliseconds':2000,'nodes':None}
        for name in ['baseline','candidate']:(pair/(name+'.json')).write_text(json.dumps(report))
        (pair/'comparison.json').write_text(json.dumps({'comparison_operational_pass':True}))

    def command(self,plan,state):return [sys.executable,str(ROOT/'scripts/run-nnue-after-measurement.py'),'--plan',str(plan),'--state',str(state)]

    def test_waits_for_complete_real_time_run_before_starting_work(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name);producer=subprocess.Popen([sys.executable,'-c','import time; time.sleep(15)'])
            watcher=None
            try:
                pair,plan,path,marker=self.fixture(folder,producer);state=folder/'state.json'
                watcher=subprocess.Popen(self.command(path,state),cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                deadline=time.monotonic()+4
                while not state.exists() and time.monotonic()<deadline:time.sleep(.02)
                self.assertTrue(state.exists());self.assertFalse(marker.exists())
                self.completed(pair,plan);self.assertEqual(watcher.wait(timeout=8),0)
                self.assertTrue(marker.exists());self.assertEqual(json.loads(state.read_text())['status'],'complete')
            finally:
                if watcher and watcher.poll() is None:watcher.terminate();watcher.wait(5)
                producer.terminate();producer.wait(5)

    def test_dead_producer_is_not_automatically_restarted(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name);producer=subprocess.Popen([sys.executable,'-c','import time; time.sleep(2)'])
            pair,plan,path,marker=self.fixture(folder,producer);producer.terminate();producer.wait(5)
            state=folder/'state.json';result=subprocess.run(self.command(path,state),cwd=ROOT,capture_output=True,timeout=8)
            self.assertNotEqual(result.returncode,0);self.assertFalse(marker.exists())
            self.assertEqual(json.loads(state.read_text())['status'],'stopped')

    def test_changed_source_is_rejected_even_after_measurement_completed(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name);producer=subprocess.Popen([sys.executable,'-c','import time; time.sleep(15)'])
            try:
                pair,plan,path,marker=self.fixture(folder,producer);plan['source_tree_sha256']='wrong'
                path.write_text(json.dumps(plan));self.completed(pair,plan);state=folder/'state.json'
                result=subprocess.run(self.command(path,state),cwd=ROOT,capture_output=True,timeout=8)
                self.assertNotEqual(result.returncode,0);self.assertFalse(marker.exists())
                self.assertIn('planned engine source changed',json.loads(state.read_text())['error'])
            finally:producer.terminate();producer.wait(5)

    def test_host_or_fixed_node_results_cannot_unlock_training(self):
        with tempfile.TemporaryDirectory() as name:
            parent=Path(name);producer=subprocess.Popen([sys.executable,'-c','import time; time.sleep(15)'])
            try:
                for key,value in [('backend','native'),('mode','fixed_nodes'),('milliseconds',1000)]:
                    folder=parent/key;folder.mkdir();pair,plan,path,marker=self.fixture(folder,producer)
                    self.completed(pair,plan);report=json.loads((pair/'candidate.json').read_text());report[key]=value
                    (pair/'candidate.json').write_text(json.dumps(report));state=folder/'state.json'
                    result=subprocess.run(self.command(path,state),cwd=ROOT,capture_output=True,timeout=8)
                    self.assertNotEqual(result.returncode,0);self.assertFalse(marker.exists())
                    self.assertIn('measurement conditions differ',json.loads(state.read_text())['error'])
            finally:producer.terminate();producer.wait(5)


if __name__=='__main__':unittest.main()
