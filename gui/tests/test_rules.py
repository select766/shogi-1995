#!/usr/bin/env python3
"""Independent move-set differential tests against python-shogi 1.1.1."""
import ctypes as C
from pathlib import Path
import random
import subprocess
import sys
import unittest
ROOT = Path(__file__).resolve().parents[2]
if len(sys.argv)>1 and sys.argv[1].startswith('--reference='):
    sys.path.insert(0,sys.argv.pop(1).split('=',1)[1])
import shogi
subprocess.run(['gcc','-std=c99','-shared','-fPIC','-O2',str(ROOT/'gui/rules.c'),'-o',str(ROOT/'.local/gui/rules.so')],check=True)
lib = C.CDLL(str(ROOT/'.local/gui/rules.so'))
class Position(C.Structure):
    _fields_=[('b',C.c_int*81),('h',(C.c_int*8)*2),('turn',C.c_int)]
class Move(C.Structure):
    _fields_=[('from_',C.c_int),('to',C.c_int),('promote',C.c_int),('drop',C.c_int)]
lib.legal.argtypes=[C.POINTER(Position),Move]
lib.apply.argtypes=[C.POINTER(Position),Move]
lib.parse_move.argtypes=[C.c_char_p,C.POINTER(Move)]
lib.read_sfen.argtypes=[C.POINTER(Position),C.c_char_p]
def load(board):
    p=Position(); assert lib.read_sfen(C.byref(p),board.sfen().encode()); return p

def legal_set(p):
    out=set();text=C.create_string_buffer(16)
    for a in range(81):
        if not p.b[a] or (p.b[a]<0)!=bool(p.turn):continue
        for b in range(81):
            for pro in range(2):
                m=Move(a,b,pro,0)
                if lib.legal(C.byref(p),m):
                    lib.move_text(m,text);out.add(text.value.decode())
    for drop in range(1,8):
        if not p.h[p.turn][drop]:continue
        for b in range(81):
            m=Move(-1,b,0,drop)
            if lib.legal(C.byref(p),m):lib.move_text(m,text);out.add(text.value.decode())
    return out

class RulesTest(unittest.TestCase):
    def test_random_complete_move_sets_and_transitions(self):
        rng=random.Random(1995)
        for game in range(5):
            board=shogi.Board();p=Position();lib.initial(C.byref(p))
            for ply in range(100):
                expected={m.usi() for m in board.legal_moves}
                self.assertEqual(legal_set(p),expected,(game,ply,board.sfen()))
                self.assertEqual(bool(lib.in_check(C.byref(p),p.turn)),board.is_check())
                self.assertEqual(bool(lib.has_legal(C.byref(p))),bool(expected))
                if not expected:break
                text=rng.choice(sorted(expected));m=Move()
                self.assertTrue(lib.parse_move(text.encode(),C.byref(m)))
                lib.apply(C.byref(p),m);board.push_usi(text)
                self.assertEqual(bytes(p),bytes(load(board)))

    def test_drop_mate_pin_and_forced_promotion(self):
        positions=[
            '3lkl3/3p1p3/4G4/9/9/9/9/9/4K4 b P 1',
            '4k4/9/4P4/9/9/9/9/9/4K4 b - 1',
            '4k4/9/9/9/9/9/4g4/4R4/4K4 b PNL 1',
            '4k4/9/9/9/9/9/9/9/4K4 b RBGSNLP 1',
        ]
        for sfen in positions:
            board=shogi.Board(sfen)
            self.assertEqual(legal_set(load(board)),{m.usi() for m in board.legal_moves},sfen)

    def test_declaration_threshold_and_check(self):
        # King + 10 pieces in camp; 27 points is insufficient for sente.
        p=load(shogi.Board('KPPPPPPPP/PPR6/9/9/9/9/9/9/4k4 b 12P 1'))
        self.assertFalse(lib.declaration(C.byref(p)))
        p.h[0][1]+=1
        self.assertTrue(lib.declaration(C.byref(p)))
        p.b[9]=-7
        self.assertFalse(lib.declaration(C.byref(p)))

    def test_malformed_moves(self):
        for text in ['', '0a1b','1a0b','K*5e','P*5e+','7g7f++','7g7f garbage']:
            self.assertFalse(lib.parse_move(text.encode(),C.byref(Move())),text)

if __name__=='__main__':unittest.main()
