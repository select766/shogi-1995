#!/usr/bin/env python3
"""Smoke-test the dedicated TsuyouraOu micro launcher on 86Box."""
import json, re, sys, time
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from shogi1995.usi import Engine
profile=ROOT/'.local/shogihome/tsuyouraou-micro-v1'
logs=ROOT/'.local/tests/tsuyouraou-micro-final'
if logs.exists(): raise SystemExit('preserve previous evidence; remove or rename log directory first')
report={'started_utc':datetime.now(timezone.utc).isoformat(),'scope':'86Box USI smoke test; not GUI play or strength measurement'}
with Engine([str(profile/'run.sh')],'/tmp',logs) as engine:
    assert engine.name=='shogi-1995 TsuyouraOu 11 micro (Pentium 100MHz)'
    assert 'default 24 ' in engine.options['FV_SCALE']
    assert 'default 2 ' in engine.options['USI_Hash']
    for opt, expected in [('FV_SCALE','24'),('USI_Hash','2'),('Threads','1'),('BookFile','no_book')]:
        engine.send('getoption '+opt); _,lines=engine.until('Options['+opt+']',10)
        assert lines[-1].split('=',1)[1].strip()==expected,lines[-1]
    engine.send('shogi1995stats'); _,lines=engine.until('info string shogi1995 memory ',10)
    report['memory_bytes']={k:int(v) for k,v in re.findall(r'(total|free|swap)=(\d+)',lines[-1])}
    assert report['memory_bytes']['swap']==0 and report['memory_bytes']['free']>0
    report['depth1']=engine.search_position('position startpos','go depth 1',30)
    report['movetime2000']=engine.search_position('position startpos','go movetime 2000',15)
    for result in (report['depth1'],report['movetime2000']):
        assert re.fullmatch(r'[1-9][a-i][1-9][a-i]\+?|[PLNSGBR]\*[1-9][a-i]',result['actual'])
    engine.send('position startpos');engine.send('go infinite');time.sleep(2);start=time.monotonic();engine.send('stop');engine.until('bestmove ',10)
    report['stop_seconds']=time.monotonic()-start
    trace=(logs/'protocol.log').read_text()
    assert 'loading eval file : /eval/nn.bin' in trace and 'loading progress file : /eval/progress.bin' in trace
report['passed']=True
report['finished_utc']=datetime.now(timezone.utc).isoformat()
report['image_sha256']=json.loads((profile/'manifest.json').read_text())['image_sha256']
(logs/'result.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2),flush=True)
