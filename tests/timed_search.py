#!/usr/bin/env python3
"""Measure ordinary USI time controls with both NetworkDelay options at zero."""
import hashlib
import json
from pathlib import Path
import queue
import re
import subprocess
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.local/tests'


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    inbox=queue.Queue()
    report={'backend':'86box','engine_sha256':hashlib.sha256((ROOT/'.local/guest-root/shogi').read_bytes()).hexdigest(),
            'options':{'NetworkDelay':0,'NetworkDelay2':0,'Threads':1,'USI_Hash':2,
                       'USI_OwnBook':False,'USI_Ponder':False},'samples':[]}
    with (OUT/'timed-search-stderr.log').open('w') as err:
        proc=subprocess.Popen([str(ROOT/'run-shogi-1995.sh')],stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,stderr=err,text=True,bufsize=1)
        def reader():
            for line in proc.stdout: inbox.put((time.monotonic(),line.rstrip()))
            inbox.put((time.monotonic(),None))
        threading.Thread(target=reader,daemon=True).start()
        def send(line): proc.stdin.write(line+'\n');proc.stdin.flush()
        def until(prefix,timeout):
            end=time.monotonic()+timeout; lines=[]
            while True:
                stamp,line=inbox.get(timeout=max(.001,end-time.monotonic()))
                if line is None: raise RuntimeError('engine exited')
                lines.append(line)
                if line.startswith(prefix): return stamp,lines
        try:
            send('usi');until('usiok',150)
            for key,value in report['options'].items():
                send(f'setoption name {key} value {str(value).lower()}')
            for repeat in range(3):
                for ms in (1000,2000,5000):
                    for mode in ('movetime','byoyomi'):
                        send('isready');until('readyok',60)
                        send('usinewgame')
                        position='position startpos' if repeat%2==0 else 'position startpos moves 7g7f 3c3d'
                        send(position)
                        command=f'go movetime {ms}' if mode=='movetime' else f'go btime 0 wtime 0 byoyomi {ms}'
                        before=(ROOT/'.local/run/usi.log').read_text().count(' > stop\n')
                        start=time.monotonic();send(command)
                        ended,lines=until('bestmove ',ms/1000+8)
                        guest=[int(m.group(1)) for line in lines if (m:=re.search(r'\btime (\d+)\b',line))]
                        stops=(ROOT/'.local/run/usi.log').read_text().count(' > stop\n')-before
                        sample={'repeat':repeat,'position':position,'command':command,'requested_ms':ms,
                                'host_elapsed_ms':round((ended-start)*1000,3),
                                'guest_reported_ms':max(guest) if guest else None,'bridge_added_stops':stops,
                                'bestmove':lines[-1].split()[1]}
                        if guest:sample['host_minus_guest_ms']=round(sample['host_elapsed_ms']-max(guest),3)
                        report['samples'].append(sample)
                        (OUT/'timed-search.json').write_text(json.dumps(report,indent=2)+'\n')
                        print(json.dumps(sample),flush=True)
                        assert stops==0
                        assert abs(sample['host_elapsed_ms']-ms) <= max(100,ms*.05),sample
                        assert guest and abs(sample['host_minus_guest_ms']) <= 100,sample
            send('quit');assert proc.wait(10)==0
            report['passed']=True
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:proc.wait(5)
                except subprocess.TimeoutExpired:proc.kill();proc.wait()
            (OUT/'timed-search.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
