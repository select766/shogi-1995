#!/usr/bin/env python3
"""Evaluate positions with Suisho5 (local engine).  usage: nodes multipv "moves..." ..."""
import subprocess, sys
R='/home/select766/shogi/shogi-1995/.local/suisho5-analysis/'
p=subprocess.Popen([R+'engine'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,cwd=R)
def send(s): p.stdin.write(s+'\n'); p.stdin.flush()
def wait(tok):
    lines=[]
    while True:
        l=p.stdout.readline()
        lines.append(l.strip())
        if l.startswith(tok): return lines
send('usi'); wait('usiok')
for k,v in [('Threads',4),('USI_Hash',512),('USI_OwnBook','false'),('FV_SCALE',24),('EvalDir',R+'official'),('MultiPV',int(sys.argv[2]))]:
    send(f'setoption name {k} value {v}')
send('isready'); wait('readyok')
for pos in sys.argv[3:]:
    send('usinewgame'); send('position startpos moves '+pos); send(f'go nodes {sys.argv[1]}')
    ls=wait('bestmove')
    print('===',pos)
    last={}
    for l in ls:
        if ' pv ' in l and 'multipv' in l:
            t=l.split(); last[t[t.index('multipv')+1]]=l
        elif ' pv ' in l: last['1']=l
    for k in sorted(last): 
        t=last[k].split(); i=t.index('score'); print(k, t[i+1], t[i+2], ' '.join(t[t.index('pv')+1:t.index('pv')+9]))
    print(ls[-1])
send('quit')
