"""Final protocol checks in the saved workspace, including rejected time controls."""
import json,sys
from pathlib import Path
import cshogi
r=Path(__file__).resolve().parent;sys.path.insert(0,str(r.parent/'src'))
from shogi1995.usi import Engine
from shogi1995.sessions import COMMON
results=[]
for compiler in ('old','modern'):
 cmd=[sys.executable,str(r/'usi.py'),'--backend','qemu','--compiler',compiler]
 with Engine(cmd,r.parent,r/'results'/('protocol-final-'+compiler),COMMON) as e:
  for prefix in ('7g7f 3c3d','7g7f 3c3d 8h2b+ 3a2b B*5e'):
   e.reset();b=cshogi.Board()
   for move in prefix.split():assert b.is_legal(b.move_from_usi(move));b.push_usi(move)
   result=e.search_position('position startpos moves '+prefix,'go depth 2',15)
   assert b.is_legal(b.move_from_usi(result['actual']));results.append(dict(compiler=compiler,history=prefix,**result))
  e.reset();result=e.search_position('position startpos','go movetime 2000',15);assert result['actual']!='resign';results.append(dict(compiler=compiler,**result))
 with Engine(cmd,r.parent,r/'results'/('protocol-reject-'+compiler),COMMON) as e:
  try:e.search_position('position startpos','go movetime 1500',10)
  except RuntimeError:results.append(dict(compiler=compiler,noninteger_time_rejected=True))
  else:raise AssertionError('unsupported time silently accepted')
(r/'results/protocol-final.json').write_text(json.dumps(results,indent=2)+'\n')
print('saved-workspace protocol checks passed')
