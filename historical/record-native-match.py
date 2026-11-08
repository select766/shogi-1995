#!/usr/bin/env python3
"""Capture an autonomous guest-GUI game; launch under a private X display."""
import argparse, ctypes, importlib.util, json, os, re, selectors, shlex, signal, subprocess, sys, time
from pathlib import Path
import cshogi
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from shogi1995.usi import Engine

class Serial:
 def __init__(self,base,process,log,run):
  self.process=process;self.log=log;self.run=run;self.buf=b'';self.counter=0;self.sel=selectors.DefaultSelector()
  self.writer=os.open(str(base)+'.in',os.O_RDWR|os.O_NONBLOCK);self.reader=os.open(str(base)+'.out',os.O_RDWR|os.O_NONBLOCK);self.sel.register(self.reader,selectors.EVENT_READ)
  spec=importlib.util.spec_from_file_location('video_bridge',ROOT/'src/bridge/main.py');self.bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.bridge);self.bridge.RUN=run
 def until(self,marker=b'gui1995# ',timeout=120,boot=False):
  deadline=time.monotonic()+timeout;next_escape=time.monotonic()+8
  while marker not in self.buf:
   if self.process.poll() is not None:raise RuntimeError('86Box exited')
   if time.monotonic()>deadline:raise TimeoutError('serial timeout '+repr(self.buf[-500:]))
   if boot and time.monotonic()>next_escape:self.bridge.bios_escape();next_escape=time.monotonic()+8
   if self.sel.select(.1):
    data=os.read(self.reader,65536)
    if data:self.buf+=data;self.log.write(data);self.log.flush()
  before,self.buf=self.buf.split(marker,1);return before.decode(errors='replace')
 def send(self,line):
  data=(line+'\n').encode()
  for i in range(0,len(data),32):
   chunk=data[i:i+32];offset=0
   while offset<len(chunk):
    try:offset+=os.write(self.writer,chunk[offset:])
    except BlockingIOError:time.sleep(.01)
   time.sleep(len(chunk)*10/115200*1.25)
 def cmd(self,line):
  self.counter+=1;marker=('__VIDEO_ACK_%d__'%self.counter).encode()
  self.send(line+'; echo '+marker.decode());before=self.until(marker=marker,timeout=30);self.until(timeout=30);return before
 def gui(self,line):return self.cmd('echo '+shlex.quote(line)+' > /tmp/shogi-gui.fifo')
 def state(self):
  for attempt in range(8):
   result=self.cmd('echo __STATE_BEGIN__; /usr/local/bin/gui-tools cat /tmp/shogi-gui.fifo.state; echo __STATE_END__')
   segment=result.split('__STATE_BEGIN__',1)[-1].split('__STATE_END__',1)[0]
   state=re.search(r'(?m)^state ([^\r\n]+)',segment);moves=re.search(r'(?m)^moves(?: ([^\r\n]*))?',segment)
   if state and moves:
    f=state.group(1).split();history=(moves.group(1) or '').split()
    if len(f)>=11 and int(f[10])==len(history):return {'turn':int(f[0]),'active':bool(int(f[1])),'status':f[7],'ply':int(f[10]),'moves':history,'board':f[5],'hands':f[6]}
   time.sleep(.2)
  raise RuntimeError('missing or incomplete GUI state '+repr(result[-600:]))
 def close(self):self.sel.close();os.close(self.reader);os.close(self.writer)

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--gnu-side',type=int,choices=(0,1),required=True);p.add_argument('--smoke-plies',type=int,default=0);a=p.parse_args()
 if a.output.exists():raise ValueError('output already exists')
 a.output.mkdir(parents=True);out=a.output.resolve();vm=out/'vm';vm.mkdir()
 subprocess.run(['cp','--reflink=auto','--sparse=always',str(ROOT/'.local/match-video/stage/root.ext2'),str(vm/'root.ext2')],check=True)
 base=vm/'console'
 for suffix in ('.in','.out'):os.mkfifo(str(base)+suffix,0o600)
 cfg=(ROOT/'config/86box/pentium100.cfg.in').read_text()
 for key,value in {'DISK':vm/'root.ext2','FIFO':base,'FLOPPY':ROOT/'.local/images/boot.img'}.items():cfg=cfg.replace('@'+key+'@',str(value))
 cfg=cfg.replace('mouse_type = none','mouse_type = ps2');(vm/'86box.cfg').write_text(cfg)
 (out/'display').write_text(os.environ['DISPLAY']);(out/'xauthority').write_text(os.environ.get('XAUTHORITY',''))
 (out/'twmrc').write_text('RandomPlacement\nNoGrabServer\nBorderWidth 3\nTitleFont "fixed"\nMenuFont "fixed"\nIconFont "fixed"\nResizeFont "fixed"\n')
 meta={'gnu_side':a.gnu_side,'status':'starting','moves':[],'backend':'86box','time':'10 seconds per move','started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'diagnostic_limit':a.smoke_plies}
 def save():
  tmp=out/'result.tmp';tmp.write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n');tmp.replace(out/'result.json')
  (out/'game.usi').write_text('startpos moves'+(' '+' '.join(meta['moves']) if meta['moves'] else '')+'\n')
 save();process=None;serial=None;recording=None;wm=None;engine=None
 try:
  wm=subprocess.Popen([str(ROOT/'.local/match-video/tools/usr/bin/twm'),'-f',str(out/'twmrc')],stdout=(out/'wm.log').open('wb'),stderr=subprocess.STDOUT,env={**os.environ,'LC_ALL':'C'})
  time.sleep(1)
  if wm.poll() is not None:raise RuntimeError('window manager failed: '+str((out/'wm.log').read_text(errors='replace')))
  recording=subprocess.Popen(['taskset','-c','7','ffmpeg','-y','-loglevel','warning','-f','x11grab','-framerate','25','-video_size','1280x960','-i',os.environ['DISPLAY'],'-an','-c:v','libx264','-preset','ultrafast','-crf','21','-pix_fmt','yuv420p',str(out/'capture.mkv')],stdin=subprocess.PIPE,stdout=(out/'record.log').open('wb'),stderr=subprocess.STDOUT)
  time.sleep(2)
  if recording.poll() is not None:raise RuntimeError('recorder failed')
  cmd=['taskset','-c','5',str(ROOT/'.local/86box/app/AppRun'),'-N','-P',str(vm),'-R',str(ROOT/'.local/86box/roms-master'),str(vm/'86box.cfg')]
  process=subprocess.Popen(cmd,stdout=(out/'vm.log').open('wb'),stderr=subprocess.STDOUT,start_new_session=True)
  serial=Serial(base,process,(out/'serial.log').open('ab',buffering=0),out);serial.until(timeout=150,boot=True)
  x=ctypes.CDLL('libX11.so.6');t=ctypes.CDLL('libXtst.so.6');x.XOpenDisplay.argtypes=[ctypes.c_char_p];x.XOpenDisplay.restype=ctypes.c_void_p;display=x.XOpenDisplay(os.environ['DISPLAY'].encode())
  if display:
   t.XTestFakeMotionEvent.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_ulong];x.XFlush.argtypes=[ctypes.c_void_p];x.XCloseDisplay.argtypes=[ctypes.c_void_p];t.XTestFakeMotionEvent(display,-1,1200,900,0);x.XFlush(display);x.XCloseDisplay(display)
  limit=time.monotonic()+60
  while True:
   if re.search(r'(?m)^GUI_READY\s*$',serial.cmd('test -p /tmp/shogi-gui.fifo && echo GUI_READY')):break
   if time.monotonic()>limit:raise TimeoutError('GUI debug FIFO not ready')
   time.sleep(.5)
  serial.gui('setup '+('human ai' if a.gnu_side==0 else 'ai human')+' 0 0');serial.gui('start')
  time.sleep(1)
  engine=Engine(['taskset','-c','4',sys.executable,str(ROOT/'historical/usi.py'),'--backend','native','--run-root',str(out)],ROOT,out/'gnu-usi',{'Threads':1,'USI_Ponder':False,'USI_OwnBook':False})
  board=cshogi.Board();meta['status']='playing';save();last_act=time.monotonic();pending=False
  while True:
   state=serial.state();guest=state['moves']
   if len(guest)<len(meta['moves']) or guest[:len(meta['moves'])]!=meta['moves']:raise RuntimeError('GUI move history disagrees: '+repr(state))
   for move in guest[len(meta['moves']):]:
    m=board.move_from_usi(move)
    if not board.is_legal(m):raise RuntimeError('illegal GUI move '+move)
    board.push(m);meta['moves'].append(move);save();last_act=time.monotonic();pending=False
   if state['ply']!=len(guest):time.sleep(.2);continue
   if not state['active']:
    terminal=state['status']
    if not terminal.startswith(('sente_wins_','gote_wins_','sente_loses_','gote_loses_','draw_')):raise RuntimeError('unexpected guest end: '+terminal)
    meta['status']='complete';meta['outcome']=terminal;save();break
   if a.smoke_plies and len(guest)>=a.smoke_plies:meta['status']='smoke_complete';save();break
   if state['turn']==a.gnu_side and not pending and state['status'] not in ('engine_starting',):
    result=engine.search_position('position startpos'+(' moves '+' '.join(guest) if guest else ''),'go btime 0 wtime 0 byoyomi 10000',90)
    move=result['actual'];meta.setdefault('gnu_thinks',[]).append(result);save()
    if move=='resign':serial.gui('action')
    elif move=='win':serial.gui('action')
    else:
     parsed=board.move_from_usi(move)
     if not board.is_legal(parsed):raise RuntimeError('GNU illegal move '+move)
     serial.gui('core move '+move)
    pending=True;last_act=time.monotonic()
   elif time.monotonic()-last_act>120:raise TimeoutError('no GUI progress')
   time.sleep(.3)
  time.sleep(4)
  serial.cmd('/usr/local/bin/gui-tools sync')
 except BaseException as exc:
  meta['status']='error';meta['error']=str(exc);save()
  raise
 finally:
  if engine:engine.close()
  if serial:serial.close()
  if process and process.poll() is None:
   os.killpg(process.pid,signal.SIGTERM)
   try:process.wait(8)
   except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
  if recording and recording.poll() is None:
   recording.stdin.write(b'q\n');recording.stdin.flush()
   try:recording.wait(20)
   except subprocess.TimeoutExpired:recording.terminate();recording.wait(5)
  if wm and wm.poll() is None:wm.terminate();wm.wait(5)
  subprocess.run(['debugfs','-R','dump /tmp/shogi-gui.log '+str(out/'guest-gui.log'),str(vm/'root.ext2')],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  save()
 print(json.dumps(meta,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
