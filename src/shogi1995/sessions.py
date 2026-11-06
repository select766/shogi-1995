"""Own two independent frozen engines for calibration and auxiliary games."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path

from .usi import Engine

ROOT = Path(__file__).resolve().parents[2]
COMMON = {'Threads':1,'USI_Hash':2,'USI_OwnBook':False,'USI_Ponder':False,'MultiPV':1,
          'MaxMovesToDraw':512,'EnteringKingRule':'CSARule27','NetworkDelay':0,'NetworkDelay2':0}


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        while chunk := f.read(1024*1024):
            h.update(chunk)
    return h.hexdigest()


def frozen_session(manifest_path, runtime, logs, native=False):
    manifest = json.loads(manifest_path.read_text())
    directory = manifest_path.parent
    options = {**COMMON, **manifest.get('engine_options', {})}
    if native:
        binary = directory/'shogi'
        if digest(binary)!=manifest['engine_sha256']:
            raise ValueError('frozen native binary hash differs')
        command = [str(binary.resolve())]
        if manifest.get('model_sha256'):
            # Older snapshots used psqt.bin; current packages use model.bin.
            model = directory/('model.bin' if (directory/'model.bin').exists() else 'psqt.bin')
            if digest(model)!=manifest['model_sha256']:
                raise ValueError('frozen native model hash differs')
            options['EvalFile'] = str(model.resolve())
    else:
        command = list(manifest['command'])
        if not command or Path(command[0]).name!='run-shogi-1995.sh' or '--image' not in command:
            raise ValueError('auxiliary real-time games require the frozen guest bridge')
        image = Path(command[command.index('--image')+1])
        if digest(image)!=manifest['image_sha256']:
            raise ValueError('frozen guest image hash differs')
        if '--run-dir' in command:
            command[command.index('--run-dir')+1] = str(runtime.resolve())
        else:
            command += ['--run-dir', str(runtime.resolve())]
    return Engine(command, ROOT, logs, options)


class Pair:
    def __init__(self, manifests, runtime, logs, native=False):
        self.engines = [None, None]
        try:
            for i,path in enumerate(manifests):
                self.engines[i] = frozen_session(path,runtime/str(i),logs/str(i),native)
        except BaseException:
            self.close()
            raise

    def close(self):
        for engine in self.engines:
            if engine is not None:
                engine.close()

    def calibrate(self, sfen, repetitions=3, milliseconds=5000, native=False):
        samples=[]
        if native:
            return {'passed':False,'skipped':'native fixed-node smoke test; no Pentium time claim'}
        with ThreadPoolExecutor(max_workers=2) as pool:
            for repeat in range(repetitions):
                for engine in self.engines:
                    engine.reset()
                futures=[pool.submit(engine.search,sfen,milliseconds) for engine in self.engines]
                results=[f.result() for f in futures]
                for i,result in enumerate(results):
                    guest=result.get('time')
                    valid=(guest is not None and abs(result['host_ms']-milliseconds)<=milliseconds*.02
                           and abs(result['host_ms']-guest)<=milliseconds*.02)
                    samples.append({'repeat':repeat,'engine':i,'requested_ms':milliseconds,
                                    'host_ms':result['host_ms'],'guest_ms':guest,'passed':valid})
        return {'passed':all(s['passed'] for s in samples),'samples':samples,
                'criterion':'both simultaneous engines: host/request and host/guest differences each <=2% of requested duration'}

    def __enter__(self):
        return self

    def __exit__(self,*args):
        self.close()
