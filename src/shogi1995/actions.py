"""Classify normal USI moves and legitimate game-ending responses."""
import re
import cshogi


def classify(board,actual):
    if actual=='resign':return {'action':'resign','legal':True}
    if actual=='win':return {'action':'declaration','legal':bool(board.is_nyugyoku(cshogi.LAW_27))}
    if not re.fullmatch(r'(?:[1-9][a-i][1-9][a-i]\+?|[PLNSGBR]\*[1-9][a-i])',actual):
        return {'action':'invalid','legal':False}
    try:legal=bool(board.is_legal(board.move_from_usi(actual)))
    except (ValueError,RuntimeError,OverflowError):legal=False
    return {'action':'move','legal':legal}
