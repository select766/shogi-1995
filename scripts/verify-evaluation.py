#!/usr/bin/env python3
"""Verify fixed records against the original HCPE, all hashes, and split isolation."""
import argparse
import hashlib
import json
from pathlib import Path
import cshogi
import numpy as np

def main():
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);args=p.parse_args()
    m=json.loads((args.directory/'manifest.json').read_text());assert m['complete']
    source=Path(m['source']);assert hashlib.sha256(source.read_bytes()).hexdigest()==m['source_sha256']
    raw=np.memmap(source,dtype=cshogi.HuffmanCodedPosAndEval,mode='r');board=cshogi.Board();sets={};ids={}
    for name,meta in m['outputs'].items():
        f=args.directory/(name+'.jsonl');assert hashlib.sha256(f.read_bytes()).hexdigest()==meta['sha256']
        rows=[json.loads(s) for s in f.read_text().splitlines()];assert len(rows)==meta['count']
        keys=set();indices=[]
        for r in rows:
            rec=raw[r['source_index']];board.set_hcp(rec['hcp'])
            assert r['sfen']==' '.join(board.sfen().split()[:3])+' 1'
            move=board.move_from_move16(int(rec['bestMove16'])&0xffff)
            assert board.is_legal(move) and cshogi.move_to_usi(move)==r['bestmove']
            key=' '.join(r['sfen'].split()[:3]);assert key not in keys
            keys.add(key);indices.append(r['source_index'])
        sets[name]=keys;ids[name]=indices
    assert ids['quick']==ids['development'][:256]
    for a,b in [('development','test'),('development','match'),('test','match')]:assert not sets[a]&sets[b]
    assert ids['development']+ids['test']+ids['match']==m['sample_source_indices']
    excluded=args.directory/'excluded-sfen.txt'
    assert hashlib.sha256(excluded.read_bytes()).hexdigest()==m['excluded_sfen_sha256']
    assert set(excluded.read_text().splitlines())==sets['development']|sets['test']|sets['match']
    print('verified all sampled labels, source hashes, split isolation, quick subset, exclusions, and sample order')

if __name__=='__main__':main()
