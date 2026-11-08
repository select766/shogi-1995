#!/usr/bin/env python3
"""Verify finished captures and saved move legality without altering them."""
import datetime,hashlib,json,subprocess,sys,time
from pathlib import Path
import cshogi
ROOT=Path(__file__).resolve().parents[1]
DIRS=[ROOT/'.local/match-video/recording-gnu-sente-02',ROOT/'.local/match-video/recording-gnu-gote-02']
deadline=datetime.datetime(2026,11,8,9,tzinfo=datetime.timezone(datetime.timedelta(hours=9)))
def verify(d,r):
 errors=[];b=cshogi.Board();moves=r['moves']
 for i,s in enumerate(moves):
  try:m=b.move_from_usi(s);valid=b.is_legal(m)
  except Exception:valid=False
  if not valid:errors.append('illegal move %d: %s'%(i+1,s));break
  b.push(m)
 if (d/'game.usi').read_text().strip()!='startpos moves'+(' '+' '.join(moves) if moves else ''):errors.append('record differs from result')
 outcome=r.get('outcome','')
 if outcome.endswith('_wins_mate') and not b.is_game_over():errors.append('mate does not match independent legal-move check')
 if outcome=='draw_move_limit' and len(moves)!=256:errors.append('unexpected move-limit count')
 media=d/'capture.mkv'
 probe=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration:stream=codec_name,width,height,codec_type','-of','json',str(media)],capture_output=True,text=True,timeout=20)
 if probe.returncode:errors.append('ffprobe failed');details={}
 else:
  details=json.loads(probe.stdout);streams=details.get('streams',[])
  if not any(x.get('codec_type')=='video' and x.get('width')==1280 and x.get('height')==960 for x in streams):errors.append('expected capture stream missing')
  if any(x.get('codec_type')=='audio' for x in streams):errors.append('unexpected audio')
  if float(details.get('format',{}).get('duration',0))<10:errors.append('capture too short')
 log=d/'guest-gui.log'
 if not log.exists():errors.append('guest GUI log not extracted')
 else:
  text=log.read_text(errors='replace')
  if 'go btime 0 wtime 0 byoyomi 10000' not in text:errors.append('guest 10-second go not found')
  for option in ('NetworkDelay value 0','NetworkDelay2 value 0'):
   if option not in text:errors.append('guest option missing: '+option)
 h=hashlib.sha256()
 with media.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 result={'status':'pass' if not errors else 'failed','errors':errors,'plies':len(moves),'outcome':outcome,'media_sha256':h.hexdigest(),'ffprobe':details}
 (d/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(d.name,result['status'],errors,flush=True)
 return not errors
pending=set(DIRS)
while pending and datetime.datetime.now(datetime.timezone.utc)<deadline:
 for d in list(pending):
  try:r=json.loads((d/'result.json').read_text())
  except (OSError,ValueError):continue
  if r.get('status')=='error':
   (d/'verification.json').write_text(json.dumps({'status':'failed','errors':[r.get('error','recording error')]},indent=2)+'\n');pending.remove(d);continue
  if r.get('status')!='complete':continue
  # Wait for recorder finalization and filesystem sync after the result is marked complete.
  if time.time()-(d/'result.json').stat().st_mtime<30:continue
  try:verify(d,r)
  except Exception as exc:(d/'verification.json').write_text(json.dumps({'status':'failed','errors':[str(exc)]},indent=2)+'\n')
  pending.remove(d)
 time.sleep(20)
