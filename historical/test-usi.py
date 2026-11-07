import json,sys,time
from pathlib import Path
import cshogi
r=Path(__file__).resolve().parent;sys.path.insert(0,str(r.parent/'src'))
from shogi1995.usi import Engine
from shogi1995.sessions import COMMON
backend=sys.argv[1] if len(sys.argv)>1 else 'qemu'
results=[]
mid=cshogi.Board(json.loads((r/'test-positions.json').read_text())[2])
for compiler in ('old','modern'):
 command=[sys.executable,str(r/'usi.py'),'--backend',backend,'--compiler',compiler]
 with Engine(command,r.parent,r/'results'/('usi-'+backend+'-'+compiler),COMMON) as e:
  for position in ('position startpos','position startpos moves 7g7f 3c3d','position startpos moves 7g7f', 'position sfen '+mid.sfen()):
   result=e.search_position(position,'go btime 0 wtime 0 byoyomi 2000',30)
   b=cshogi.Board()
   if 'sfen' in position:b.set_sfen(position.split('sfen ')[1])
   elif 'moves' in position:
    for m in position.split('moves ')[1].split():b.push_usi(m)
   assert b.is_legal(b.move_from_usi(result['actual'])),result
   results.append(dict(compiler=compiler,position=position,**result));(r/'results'/('usi-'+backend+'.json')).write_text(json.dumps(results,indent=2)+'\n');print(compiler,position,result,flush=True)
  for repeat in range(2):
   e.reset()
   result=e.search_position('position startpos moves 7g7f 3c3d','go depth 4',60)
   results.append(dict(compiler=compiler,fixed_depth=4,repeat=repeat,**result));print(compiler,'fixed-depth',result,flush=True)
  e.send('position startpos');e.send('go infinite');time.sleep(.25);start=time.monotonic();e.send('stop');_,lines=e.until('bestmove ',5);stop_ms=(time.monotonic()-start)*1000
  assert cshogi.Board().is_legal(cshogi.Board().move_from_usi(lines[-1].split()[1]))
  results.append(dict(compiler=compiler,stop_ms=stop_ms))
(r/'results'/('usi-'+backend+'.json')).write_text(json.dumps(results,indent=2)+'\n')
