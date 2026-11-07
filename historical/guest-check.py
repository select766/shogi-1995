#!/usr/bin/env python3
"""Compare the two compiler builds in one isolated Linux 1.2.13 VM."""
import subprocess,selectors,os,time,re,json
from pathlib import Path
import cshogi
r=Path(__file__).resolve().parent
os.environ['TMPDIR']='/tmp'
p=subprocess.Popen(['nice','-n','19','qemu-system-i386','-machine','pc','-cpu','pentium','-m','32','-snapshot','-kernel',str(r/'guest-vmlinuz'),'-append','root=/dev/hda rw','-drive',f'file={r}/guest.ext2,format=raw,if=ide','-display','none','-serial','stdio','-monitor','none','-no-reboot','-net','none'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
s=selectors.DefaultSelector();s.register(p.stdout,selectors.EVENT_READ);buf=b'';log=b''
def until(pattern,timeout=30):
 global buf,log
 end=time.monotonic()+timeout
 while True:
  m=re.search(pattern,buf)
  if m: data=buf[:m.end()];buf=buf[m.end():];return data
  if time.monotonic()>end:raise TimeoutError(buf[-1000:])
  if s.select(.1):
   b=os.read(p.stdout.fileno(),65536)
   if not b:raise RuntimeError(buf[-1000:])
   buf+=b;log+=b
def send(cmd):p.stdin.write((cmd+'\n').encode());p.stdin.flush()
def setup(sfen):
 board,side,hand,_=sfen.split();cmd=['edit','#'];placements=[[],[]]
 for rank,row in enumerate(board.split('/')):
  file=9;promote=False
  for ch in row:
   if ch.isdigit():file-=int(ch)
   elif ch=='+':promote=True
   else:
    placements[ch.islower()].append(ch.upper()+str(file)+chr(97+rank)+('+' if promote else ''));file-=1;promote=False
 n=''
 for ch in hand:
  if ch.isdigit():n+=ch
  elif ch!='-':placements[ch.islower()]+=[ch.upper()+'*']*int(n or '1');n=''
 cmd+=placements[0]+['c']+placements[1]+['.'];send('\n'.join(cmd));until(rb'Your move is\?')
 send('black' if side=='b' else 'white');until(rb'Your move is\?')
records=[]; selfplay=[]; timings=[]
positions=json.loads((r/'test-positions.json').read_text())
try:
 until(rb'guest1995# ')
 for variant in ('old','modern'):
  for idx,sfen in enumerate(positions):
   for repeat in range(2):
    send('/work/'+variant+('/src' if variant=='old' else '')+'/gnushogir -b /dev/null -B /work/empty-book 60')
    until(rb'Your move is\?')
    setup(sfen)
    for cmd in ('level 0 1:00','depth\n4','post'):
     send(cmd);until(rb'Your move is\?')
    start=time.monotonic();send('go');out=until(rb'Your move is\?',60);elapsed=time.monotonic()-start
    move=re.search(rb'GNU_RESULT move=(\S+)',out)[1].decode();board=cshogi.Board(sfen);assert board.is_legal(board.move_from_usi(move)),(sfen,move)
    stats=re.search(rb'Gen (\d+) Node (\d+).*Eval (\d+)',out)
    records.append(dict(variant=variant,position=idx,repeat=repeat,sfen=sfen,usi=move,seconds=elapsed,nodes=int(stats[2]),evals=int(stats[3])))
    send('quit');until(rb'guest1995# ')
    print(variant,idx,repeat,move,records[-1]['nodes'],round(elapsed,3),flush=True)
 for variant in ('old','modern'):
  command='/work/'+variant+('/src' if variant=='old' else '')+'/gnushogir -b /dev/null -B /work/empty-book 60'
  send(command);until(rb'Your move is\?')
  for cmd in ('level 0 0:01','depth\n2'):
   send(cmd);until(rb'Your move is\?')
  board=cshogi.Board();moves=[]
  for ply in range(160):
   if board.is_game_over():break
   send('go' if ply==0 else 'switch');out=until(rb'Your move is\?')
   move=re.search(rb'GNU_RESULT move=(\S+)',out)[1].decode()
   assert board.is_legal(board.move_from_usi(move)),(variant,ply,move,board.sfen())
   board.push_usi(move);moves.append(move)
  selfplay.append(dict(variant=variant,legal_plies=len(moves),drops=sum('*' in m for m in moves),promotions=sum('+' in m for m in moves),moves=moves))
  send('quit');until(rb'guest1995# ')
  for seconds in (1,2):
   for repeat in range(3):
    send(command);until(rb'Your move is\?')
    send('level 0 0:'+str(seconds));until(rb'Your move is\?')
    start=time.monotonic();send('go');out=until(rb'Your move is\?');elapsed=time.monotonic()-start
    move=re.search(rb'GNU_RESULT move=(\S+)',out)[1].decode();board=cshogi.Board();assert board.is_legal(board.move_from_usi(move))
    timings.append(dict(variant=variant,requested_seconds=seconds,elapsed_seconds=elapsed,usi=move))
    send('quit');until(rb'guest1995# ')
  print(variant,'selfplay and timing passed',flush=True)
finally:
 (r/'results/guest-check.log').write_bytes(log)
 (r/'results/compiler-comparison.json').write_text(json.dumps(dict(environment='QEMU diagnostic, Linux 1.2.13, 32MiB, NOT Pentium timing',depth=4,records=records,selfplay=selfplay,timings=timings),indent=2)+'\n')
 p.terminate();p.wait(timeout=10)
