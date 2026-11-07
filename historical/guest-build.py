import subprocess,selectors,os,time
from pathlib import Path
r=Path(__file__).resolve().parent
p=subprocess.Popen(['nice','-n','19','qemu-system-i386','-machine','pc','-cpu','pentium','-m','32','-kernel',str(r/'guest-vmlinuz'),'-append','root=/dev/hda rw','-drive',f'file={r}/guest.ext2,format=raw,if=ide','-display','none','-serial','stdio','-monitor','none','-no-reboot','-net','none'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
s=selectors.DefaultSelector();s.register(p.stdout,selectors.EVENT_READ);data=b''
def until(needle,timeout=90):
 global data
 end=time.monotonic()+timeout
 while needle not in data:
  if time.monotonic()>end:raise TimeoutError(data[-1000:])
  if s.select(.1):
   b=os.read(p.stdout.fileno(),65536)
   if not b:raise RuntimeError(data[-1000:])
   data+=b
try:
 until(b'guest1995# ')
 p.stdin.write(b'/bin/bash /work/build.sh\n');p.stdin.flush()
 until(b'BUILD_FINISHED')
 for marker in (b'OLD_BUILD_EXIT=0',b'MODERN_LINK_EXIT=0',b'RELAY_BUILD_EXIT=0',b'SYNC_EXIT=0'):
  if marker not in data:raise RuntimeError('guest build did not report success: '+repr(marker))
 time.sleep(3);print(data.decode(errors='replace'))
finally:
 (r/'results/guest-build.log').write_bytes(data);p.terminate();p.wait(timeout=10)
