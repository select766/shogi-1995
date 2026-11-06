"""YaneuraOu HalfKP(Friend), fe_end=1548, without DISTINGUISH_GOLDS.

Index = oriented own king square * fe_end + BonaPiece. Hand pieces use
distinct ordinal slots; gold-like promoted minors share the gold category.
The order of active indices is immaterial for their sum.
"""
import numpy as np

STRIDE = 1548
INPUTS = 81 * STRIDE
ACTIVE = 38
HAND_FIRST = ((1,39,49,59,69,79,85), (20,44,54,64,74,82,88))
BOARD_GROUP = {1:0,2:1,3:2,4:3,7:4,9:4,10:4,11:4,12:4,5:5,13:6,6:7,14:8}


def encode(board):
    pieces = board.pieces
    hands = board.pieces_in_hand
    kings = (pieces.index(8), pieces.index(24))
    result = np.empty((2,ACTIVE), dtype=np.int32)
    for perspective in range(2):
        king = kings[perspective] if perspective == 0 else 80-kings[perspective]
        offset = king * STRIDE
        indices = []
        for square,piece in enumerate(pieces):
            if not piece or (piece & 15) == 8:
                continue
            relative = int((piece >= 16) != bool(perspective))
            oriented = square if perspective == 0 else 80-square
            indices.append(offset+90+(BOARD_GROUP[piece & 15]*2+relative)*81+oriented)
        for color in range(2):
            relative = int(color != perspective)
            for kind,count in enumerate(hands[color]):
                indices.extend(offset+HAND_FIRST[relative][kind]+ordinal for ordinal in range(count))
        if len(indices)>ACTIVE:
            raise ValueError('too many non-king pieces')
        indices.extend([offset]*(ACTIVE-len(indices)))
        result[perspective] = indices
    return result if board.turn == 0 else result[::-1].copy()


def material_initial_weights():
    """Shared weights initialized so perspective difference equals material."""
    values = np.zeros(STRIDE,dtype=np.float32)
    board_values = (90,315,405,495,540,855,945,990,1395)
    hand_values = (90,315,405,495,540,855,990)
    maxima = (18,4,4,4,4,2,2)
    for relative in range(2):
        sign = 1 if relative == 0 else -1
        for group,value in enumerate(board_values):
            start = 90+(group*2+relative)*81
            values[start:start+81] = sign*value/2
        for kind,(value,maximum) in enumerate(zip(hand_values,maxima)):
            start = HAND_FIRST[relative][kind]
            values[start:start+maximum] = sign*value/2
    return np.tile(values,81)
