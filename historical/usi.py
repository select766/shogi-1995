#!/usr/bin/env python3
"""USI adapter for historical GNU Shogi. No search/evaluation changes.
Fixed integer-second byoyomi/movetime only; no hidden margin or host deadline stop.
"""
import argparse,hashlib,ctypes,importlib.util,json,os,queue,re,selectors,signal,subprocess,sys,tempfile,threading,time
from pathlib import Path
import cshogi
HERE=Path(__file__).resolve().parent
PROMPT=rb'Your move is\?'
FIXED={'Threads':'1','USI_Hash':'2','USI_OwnBook':'false','USI_Ponder':'false','MultiPV':'1','MaxMovesToDraw':'512','EnteringKingRule':'CSARule27','NetworkDelay':'0','NetworkDelay2':'0'}
def emit(s):print(s,flush=True)
class Transport:
 def __init__(self,args):
  manifest=json.loads((HERE/('manifest-'+args.compiler+'.json')).read_text())
  for file,key in [('guest.ext2','image_sha256'),('guest-vmlinuz','guest_kernel_sha256')]:
   if hashlib.sha256((HERE/file).read_bytes()).hexdigest()!=manifest[key]:raise ValueError('frozen artifact hash mismatch: '+file)
  self.args=args;self.temp=tempfile.TemporaryDirectory(prefix='gnushogi-usi-',dir=args.run_root);self.run=Path(self.temp.name);self.buf=b'';self.fds=[];self.sel=selectors.DefaultSelector();self.log=(self.run/'transport.log').open('wb');self.events=(self.run/'commands.log').open('w',buffering=1);self.p=None
  print('GNU Shogi isolated runtime: '+str(self.run),file=sys.stderr,flush=True)
  try:
   if args.backend=='qemu':
    env={**os.environ,'TMPDIR':str(self.run)}
    self.p=subprocess.Popen(['nice','-n','19','qemu-system-i386','-machine','pc','-cpu','pentium','-m','32','-snapshot','-kernel',str(HERE/'guest-vmlinuz'),'-append','root=/dev/hda rw','-drive',f'file={HERE}/guest.ext2,format=raw,if=ide','-display','none','-serial','stdio','-monitor','none','-no-reboot','-net','none'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.log,start_new_session=True,env=env)
    self.reader=self.p.stdout.fileno();self.writer=self.p.stdin.fileno()
   else:
    root=args.research_root;vm=self.run/'vm';vm.mkdir();disk=vm/'root.ext2';subprocess.run(['cp','--sparse=always',str(HERE/'guest.ext2'),str(disk)],check=True)
    fifo=vm/'usi'
    for suffix in ('.in','.out'):os.mkfifo(str(fifo)+suffix,0o600)
    self.writer=os.open(str(fifo)+'.in',os.O_RDWR|os.O_NONBLOCK);self.reader=os.open(str(fifo)+'.out',os.O_RDWR|os.O_NONBLOCK);self.fds=[self.reader,self.writer]
    cfg=(root/'config/86box/pentium100.cfg.in').read_text()
    for key,val in {'DISK':disk,'FIFO':fifo,'FLOPPY':root/'.local/images/boot.img'}.items():cfg=cfg.replace('@'+key+'@',str(val))
    (vm/'86box.cfg').write_text(cfg)
    spec=importlib.util.spec_from_file_location('legacy_transport',root/'src/bridge/main.py');self.bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.bridge);self.bridge.RUN=self.run
    self.p=subprocess.Popen(['nice','-n','19','xvfb-run','-a','bash',str(root/'scripts/launch-86box.sh'),str(self.run)],cwd=root,stdout=self.log,stderr=self.log,start_new_session=True)
   os.set_blocking(self.reader,False);self.sel.register(self.reader,selectors.EVENT_READ)
   started=time.monotonic();last_escape=started
   def boot():
    nonlocal last_escape
    if args.backend=='86box' and time.monotonic()-last_escape>5:self.bridge.bios_escape();last_escape=time.monotonic()
   self.until(rb'guest1995# ',150,boot)
  except BaseException:self.close();raise
 def send(self,text):
  self.events.write(f'{time.monotonic():.6f} > {text}\n');data=(text+'\n').encode()
  for i in range(0,len(data),32):
   part=data[i:i+32];offset=0
   while offset<len(part):
    try:offset+=os.write(self.writer,part[offset:])
    except BlockingIOError:time.sleep(.001)
   if self.args.backend=='86box':time.sleep(len(part)*10/115200*1.25)
 def until(self,pattern,timeout=30,callback=None):
  end=time.monotonic()+timeout
  while True:
   m=re.search(pattern,self.buf)
   if m:out=self.buf[:m.end()];self.buf=self.buf[m.end():];return out
   if callback:callback()
   if time.monotonic()>end:raise TimeoutError('guest response timeout: '+repr(self.buf[-300:]))
   if self.p.poll() is not None:raise RuntimeError('guest exited')
   if self.sel.select(.005):
    b=os.read(self.reader,65536)
    if not b:raise RuntimeError('guest stream closed')
    self.buf+=b;self.log.write(b);self.log.flush()
    if len(self.buf)>4*1024*1024:raise RuntimeError('guest output exceeded limit')
 def cmd(self,text):
  self.send(text);out=self.until(PROMPT)
  if b'Illegal move' in out or b'Command not found' in out:raise RuntimeError(out.decode(errors='replace'))
  return out
 def close(self):
  if self.p and self.p.poll() is None:
   os.killpg(self.p.pid,signal.SIGTERM)
   try:self.p.wait(3)
   except subprocess.TimeoutExpired:os.killpg(self.p.pid,signal.SIGKILL);self.p.wait()
  self.sel.close()
  for fd in self.fds:os.close(fd)
  self.log.close();self.events.close()
  # Keep logs for audit; TemporaryDirectory would otherwise remove them.
  self.temp._finalizer.detach()

def edit_commands(sfen):
 board,side,hand,_=sfen.split();placements=[[],[]]
 for rank,row in enumerate(board.split('/')):
  file=9;promote=False
  for ch in row:
   if ch.isdigit():file-=int(ch)
   elif ch=='+':promote=True
   else:placements[ch.islower()].append(ch.upper()+str(file)+chr(97+rank)+('+' if promote else ''));file-=1;promote=False
 n=''
 for ch in hand:
  if ch.isdigit():n+=ch
  elif ch!='-':placements[ch.islower()]+=[ch.upper()+'*']*int(n or 1);n=''
 return '\n'.join(['edit','#']+placements[0]+['c']+placements[1]+['.'])
class Adapter:
 def __init__(self,args):self.args=args;self.t=None;self.live=False;self.board=None;self.queue=queue.Queue();self.position=None
 def ready(self):
  if self.t is None:self.t=Transport(self.args)
  if self.live:self.t.send('quit');self.t.until(rb'guest1995# ')
  path='/work/old/src/gnushogir' if self.args.compiler=='old' else '/work/modern/gnushogir'
  self.t.send('/work/relay '+path+' -b /dev/null -B /tmp/usi-empty-book 2');self.t.until(PROMPT);self.live=True;self.board=None
 def set_position(self,line):
  if not self.live:self.ready()
  tokens=line.split();idx=tokens.index('moves') if 'moves' in tokens else len(tokens)
  if tokens[1]=='startpos':base=cshogi.STARTING_SFEN
  elif tokens[1]=='sfen' and idx==6:base=' '.join(tokens[2:6])
  else:raise ValueError('unsupported position syntax')
  board=cshogi.Board(base);moves=tokens[idx+1:]
  for move in moves:
   parsed=board.move_from_usi(move)
   if not board.is_legal(parsed):raise ValueError('illegal input move '+move)
   board.push(parsed)
  self.t.cmd('new');self.t.cmd(edit_commands(base));self.t.cmd('black' if base.split()[1]=='b' else 'white')
  if moves:
   self.t.cmd('force')
   for move in moves:self.t.cmd(move)
  self.t.cmd('black' if board.turn==0 else 'white')
  state=self.t.cmd('adapterstate')
  match=re.search(rb'GNU_STATE side=(\d+) gamecnt=(\d+) board=([0-9,-]+) hand=([0-9,]+)',state)
  if not match:raise RuntimeError('position readback missing')
  codes={'P':1,'L':2,'N':3,'S':4,'G':5,'B':6,'R':7,'K':14,'+P':8,'+L':9,'+N':10,'+S':11,'+B':12,'+R':13}
  squares=[];promote=False
  for ch in board.sfen().split()[0]:
   if ch=='/':continue
   if ch.isdigit():squares += [0]*int(ch)
   elif ch=='+':promote=True
   else:squares.append(codes[('+' if promote else '')+ch.upper()] * (-1 if ch.islower() else 1));promote=False
  hands=[0]*14;n=''
  for ch in board.sfen().split()[2]:
   if ch.isdigit():n+=ch
   elif ch!='-':hands[7*ch.islower()+codes[ch.upper()]-1]=int(n or 1);n=''
  actual=lambda x:[int(v) for v in x.decode().strip(',').split(',')]
  if int(match[1])!=board.turn or int(match[2])!=len(moves) or actual(match[3])!=squares or actual(match[4])!=hands:raise RuntimeError('guest position differs from requested SFEN/history')
  self.t.cmd('post');self.board=board;self.position=line
 def go(self,line):
  if self.board is None:raise ValueError('position required before go')
  tokens=line.split()[1:];depth=29;milliseconds=None
  if tokens==['infinite']:milliseconds=3600000
  elif len(tokens)==2 and tokens[0]=='depth':depth=int(tokens[1]);milliseconds=60000
  else:
   if len(tokens)%2:raise ValueError('unsupported go command')
   values=dict(zip(tokens[::2],tokens[1::2]))
   if set(values)=={'movetime'}:milliseconds=int(values['movetime'])
   elif set(values)<= {'btime','wtime','byoyomi'} and 'byoyomi' in values and int(values.get('btime',0))==int(values.get('wtime',0))==0:milliseconds=int(values['byoyomi'])
   else:raise ValueError('only zero-clock byoyomi or movetime supported; Fischer/main-time allocation is not mapped')
  if milliseconds<1000 or milliseconds%1000 or not 2<=depth<=29:raise ValueError('historical time control requires whole seconds >=1; depth 2..29')
  seconds=milliseconds//1000
  self.t.cmd(f'level 0 {seconds//60}:{seconds%60:02d}');self.t.cmd('depth\n'+str(depth))
  stopped=False;quit_requested=False
  def control():
   nonlocal stopped,quit_requested
   while True:
    try:command=self.queue.get_nowait()
    except queue.Empty:return
    if command in ('stop','quit',None):
     if not stopped:self.t.send('__STOP__');stopped=True
     if command in ('quit',None):quit_requested=True
    else:raise ValueError('unexpected command during search: '+command)
  start=time.monotonic();self.t.send('go');out=self.t.until(PROMPT,max(30,milliseconds/1000+20),control)
  m=re.search(rb'GNU_RESULT move=(\S+) time_cs=(\d+) nodes=(\d+) depth=(\d+)',out)
  if not m:raise RuntimeError('GNU_RESULT missing: '+out[-500:].decode(errors='replace'))
  move=m[1].decode()
  if move!='resign' and not self.board.is_legal(self.board.move_from_usi(move)):raise RuntimeError('GNU Shogi produced illegal move '+move)
  emit(f'info depth {int(m[4])} time {int(m[2])*10} nodes {int(m[3])}')
  emit(f'info string gnushogi adapter_search_ms={(time.monotonic()-start)*1000:.3f} requested_ms={milliseconds} explicit_stop={str(stopped).lower()}')
  emit('bestmove '+move)
  if quit_requested:raise EOFError
 def run(self):
  def read():
   for line in sys.stdin:self.queue.put(line.strip())
   self.queue.put(None)
  threading.Thread(target=read,daemon=True).start()
  try:
   while True:
    line=self.queue.get()
    if line is None or line=='quit':break
    if line=='usi':
     emit('id name GNU Shogi 1.2p03 GCC '+json.loads((HERE/('manifest-'+self.args.compiler+'.json')).read_text())['compiler'].removeprefix('GCC ')+' adapter')
     emit('id author Matthias Mutz; historical USI adapter')
     for name,value in FIXED.items():
      kind=('check default '+value if value in ('true','false') else 'spin default '+value+' min '+value+' max '+value if value.isdigit() else 'combo default '+value+' var '+value)
      emit('option name '+name+' type '+kind)
     emit('info string USI_Hash is a compatibility token; historical table sizes remain fixed. Rules/max-plies adjudicated by host.')
     emit('usiok')
    elif line=='isready':self.ready();emit('readyok')
    elif line.startswith('setoption '):
     m=re.fullmatch(r'setoption name (.+) value (.+)',line)
     if not m or FIXED.get(m[1])!=m[2]:raise ValueError('unsupported option/value: '+line)
    elif line.startswith('position '):self.set_position(line)
    elif line.startswith('go '):self.go(line)
    elif line in ('usinewgame','stop') or line.startswith('gameover '):pass
    else:raise ValueError('unsupported USI command: '+line)
  except EOFError:pass
  finally:
   if self.t:self.t.close()
def main():
 p=argparse.ArgumentParser();p.add_argument('--backend',choices=('qemu','86box'),default='86box');p.add_argument('--compiler',choices=('old','modern'),default='old');p.add_argument('--research-root',type=Path,default=HERE.parent);p.add_argument('--run-root',type=Path,default=HERE/'runs');args=p.parse_args();args.run_root.mkdir(parents=True,exist_ok=True)
 def terminate(signum,frame):raise SystemExit(128+signum)
 signal.signal(signal.SIGTERM,terminate)
 Adapter(args).run()
if __name__=='__main__':
 try:main()
 except (ValueError,RuntimeError,TimeoutError,OSError) as e:
  print('GNU Shogi USI error: '+str(e),file=sys.stderr,flush=True);sys.exit(1)
