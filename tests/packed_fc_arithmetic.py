#!/usr/bin/env python3
"""Exercise the actual C++ pair helper against independent arbitrary-precision sums."""
import argparse
from datetime import datetime, timezone
import hashlib
import itertools
import json
from pathlib import Path
import random
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('preserve previous evidence')
    seed = 20261106
    cases = list(itertools.product((0,1,63,64,127,128),(0,1,63,64,127,128),
                                   (-128,-127,-1,0,1,126,127),(-128,-127,-1,0,1,126,127)))
    rng = random.Random(seed)
    cases += [(rng.randrange(129),rng.randrange(129),rng.randrange(-128,128),rng.randrange(-128,128))
              for _ in range(8192)]
    source = r'''#include <cstdio>
#include "eval/material/shogi1995_packed_fc.h"
int main() {
    int a,b,u,v;
    while(std::scanf("%d %d %d %d",&a,&b,&u,&v)==4)
        std::printf("%d\n",YaneuraOu::Eval::PackedFC::dot(
            YaneuraOu::Eval::PackedFC::activation(a,b),YaneuraOu::Eval::PackedFC::coefficients(u,v)));
}
'''
    with tempfile.TemporaryDirectory() as folder:
        work = Path(folder)
        (work/'test.cpp').write_text(source)
        subprocess.run(['g++','-std=c++17','-O2','-fsanitize=undefined','-fno-sanitize-recover=all',
                        '-I',str(ROOT/'vendor/YaneuraOu/source'),str(work/'test.cpp'),'-o',str(work/'test')],check=True)
        result = subprocess.run([str(work/'test')],input=''.join(' '.join(map(str,row))+'\n' for row in cases),
                                capture_output=True,text=True,check=True)
        actual = list(map(int,result.stdout.splitlines()))
        assert not result.stderr and len(actual)==len(cases)
        for row,value in zip(cases,actual):
            a,b,u,v=row
            assert value==a*u+b*v,(row,value,a*u+b*v)
    header=ROOT/'vendor/YaneuraOu/source/eval/material/shogi1995_packed_fc.h'
    report={'passed':True,'verified_at_utc':datetime.now(timezone.utc).isoformat(),'seed':seed,
            'cases':len(cases),'undefined_behavior_sanitizer_passed':True,
            'helper_sha256':hashlib.sha256(header.read_bytes()).hexdigest(),
            'test_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'scope':'native C++ helper arithmetic only; no Pentium execution, speed or strength claim'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
