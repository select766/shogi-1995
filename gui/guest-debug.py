#!/usr/bin/env python3
"""Serial console and QMP diagnostics for the isolated QEMU GUI guest."""
import argparse
import json
from pathlib import Path
import socket
import time
ROOT=Path(__file__).resolve().parent.parent
class Guest:
    def __init__(self,run=None):
        self.run=run or ROOT/'.local/gui/run'
        self.serial=socket.socket(socket.AF_UNIX)
        self.serial.connect(str(self.run/'serial.sock'));self.serial.settimeout(.1)
        self.pending=b''
    def read_until(self,marker=b'gui1995# ',timeout=20):
        end=time.monotonic()+timeout
        while marker not in self.pending:
            if time.monotonic()>end:raise TimeoutError(self.pending.decode(errors='replace'))
            try:
                data=self.serial.recv(65536)
                if not data:raise EOFError('Guest serial disconnected')
                self.pending+=data
            except socket.timeout:pass
        before,self.pending=self.pending.split(marker,1)
        return before.decode(errors='replace')
    def command(self,s,timeout=20):
        self.serial.sendall(s.encode()+b'\n')
        return self.read_until(timeout=timeout)
    def gui(self,s):
        # Only caller-authored debug commands; quote the shell argument literally.
        import shlex
        return self.command('echo '+shlex.quote(s)+' > /tmp/shogi-gui.fifo')
    def state(self):
        return self.command('/usr/local/bin/gui-tools cat /tmp/shogi-gui.fifo.state')
    def screenshot(self,path):
        q=socket.socket(socket.AF_UNIX);q.connect(str(self.run/'qmp.sock'));f=q.makefile('rwb')
        def execute(name,args=None):
            obj={'execute':name}
            if args:obj['arguments']=args
            f.write(json.dumps(obj).encode()+b'\n');f.flush()
            while True:
                r=json.loads(f.readline())
                if 'error' in r:raise RuntimeError(r)
                if 'return' in r:return r
        f.readline();execute('qmp_capabilities')
        execute('screendump',{'filename':str(Path(path).resolve())});f.close();q.close()
    def close(self):self.serial.close()

def main():
    p=argparse.ArgumentParser();p.add_argument('--command');p.add_argument('--gui');p.add_argument('--screenshot',type=Path);p.add_argument('--boot',action='store_true');a=p.parse_args()
    g=Guest()
    try:
        if a.boot:print(g.read_until(),end='')
        else:print(g.command('echo connected'),end='')
        if a.command:print(g.command(a.command),end='')
        if a.gui:print(g.gui(a.gui),end='')
        if a.screenshot:g.screenshot(a.screenshot)
    finally:g.close()
if __name__=='__main__':main()
