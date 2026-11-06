"""USI subprocess client with bounded waits, complete traces, and owned-process cleanup."""
from pathlib import Path
import queue
import re
import subprocess
import threading
import time


class Engine:
    def __init__(self,command,cwd,log_dir,options=None):
        self.log_dir=Path(log_dir);self.log_dir.mkdir(parents=True,exist_ok=True)
        self.stderr=(self.log_dir/'stderr.log').open('a')
        self.trace=(self.log_dir/'protocol.log').open('a',buffering=1)
        self.queue=queue.Queue();self.options={};self.name=''
        self.process=subprocess.Popen(command,cwd=cwd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                      stderr=self.stderr,text=True,bufsize=1)
        def read():
            for line in self.process.stdout:
                line=line.rstrip('\r\n');stamp=time.monotonic()
                self.trace.write(f'{stamp:.6f} < {line}\n')
                self.queue.put((stamp,line))
            self.queue.put((time.monotonic(),None))
        self.reader=threading.Thread(target=read,daemon=True);self.reader.start()
        try:
            self.send('usi');_,lines=self.until('usiok',150)
            for line in lines:
                if line.startswith('id name '):self.name=line[8:]
                m=re.match(r'option name (.*?) type ',line)
                if m:self.options[m[1]]=line
            for key,value in (options or {}).items():
                if key not in self.options:raise ValueError(f'unsupported option {key}')
                encoded=str(value).lower() if isinstance(value,bool) else str(value)
                self.send(f'setoption name {key} value {encoded}')
            self.reset()
        except BaseException:
            self.close();raise

    def send(self,line):
        self.trace.write(f'{time.monotonic():.6f} > {line}\n')
        self.process.stdin.write(line+'\n');self.process.stdin.flush()

    def until(self,prefix,timeout):
        deadline=time.monotonic()+timeout;lines=[]
        while True:
            if time.monotonic()>=deadline:raise TimeoutError(f'waiting for {prefix}')
            try:stamp,line=self.queue.get(timeout=max(.001,deadline-time.monotonic()))
            except queue.Empty:raise TimeoutError(f'waiting for {prefix}') from None
            if line is None:raise RuntimeError(f'engine exited ({self.process.poll()})')
            lines.append(line)
            if line.startswith(prefix):return stamp,lines

    def reset(self):
        self.send('isready');self.until('readyok',60);self.send('usinewgame')

    def search(self,sfen,milliseconds=2000,nodes=None,diagnostics=False):
        self.send('position sfen '+sfen)
        command=f'go nodes {nodes}' if nodes is not None else f'go btime 0 wtime 0 byoyomi {milliseconds}'
        started=time.monotonic();self.send(command)
        try:ended,lines=self.until('bestmove ',max(10,milliseconds/1000+5) if nodes is None else 120)
        except TimeoutError:
            self.send('stop')
            try:self.until('bestmove ',3)
            except (TimeoutError,RuntimeError):pass
            raise
        result={'actual':lines[-1].split()[1],'host_ms':(ended-started)*1000,'go':command}
        for line in lines:
            if not line.startswith('info '):continue
            for key in ('time','nodes','nps','depth','seldepth'):
                m=re.search(r'\b'+key+r' (\d+)\b',line)
                if m:result[key]=int(m[1])
        if diagnostics:
            self.send('shogi1995searchstats')
            _,stats=self.until('info string shogi1995 search ',10)
            values={key:int(value) for key,value in (item.split('=') for item in stats[-1].split()[4:])}
            result.update(completed_depth=values['completed_depth'],final_nodes=values['nodes'],final_time=values['time'])
            result['final_nps']=values['nodes']*1000//max(1,values['time'])
        return result

    def close(self):
        if self.process.poll() is None:
            try:self.send('quit');self.process.wait(5)
            except (BrokenPipeError,OSError,subprocess.TimeoutExpired):
                self.process.terminate()
                try:self.process.wait(5)
                except subprocess.TimeoutExpired:self.process.kill();self.process.wait()
        self.reader.join(1)
        self.trace.close();self.stderr.close()

    def __enter__(self):return self
    def __exit__(self,*args):self.close()
