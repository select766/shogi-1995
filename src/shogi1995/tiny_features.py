"""King-conditioned features for the project's scalar, compact evaluator."""
import numpy as np

STRIDE = 2120
INPUTS = 81 * STRIDE
SYMMETRIC_INPUTS = 45 * STRIDE
ACTIVE = 38
TYPES = [1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 14]
TYPE_INDEX = {piece: i for i, piece in enumerate(TYPES)}
VALUES = [0, 90, 315, 405, 495, 855, 990, 540, 0, 540, 540, 540, 540, 945, 1395]
HAND_VALUES = [90, 315, 405, 495, 540, 855, 990]


def encode(board, symmetric=False):
    pieces = board.pieces
    hands = board.pieces_in_hand
    kings = [pieces.index(8), pieces.index(24)]
    features = np.full((2, ACTIVE), SYMMETRIC_INPUTS if symmetric else INPUTS, dtype=np.int32)
    material = sum((-1 if p >= 16 else 1) * VALUES[p & 15] for p in pieces if p)
    material += sum((hands[0][i] - hands[1][i]) * HAND_VALUES[i] for i in range(7))
    for perspective in range(2):
        king = 80 - kings[perspective] if perspective else kings[perspective]
        king_file,king_rank=divmod(king,9)
        mirror=symmetric and king_file>4
        king_index=king_rank*5+min(king_file,8-king_file) if symmetric else king
        indices = []
        for square, piece in enumerate(pieces):
            if not piece or (piece & 15) == 8:
                continue
            relative = int((piece >= 16) != bool(perspective))
            square = 80 - square if perspective else square
            if mirror:square=(8-square//9)*9+square%9
            indices.append(king_index * STRIDE + (relative * 13 + TYPE_INDEX[piece & 15]) * 81 + square)
        for color in range(2):
            relative = int(color != perspective)
            for pt, count in enumerate(hands[color]):
                indices.extend([king_index * STRIDE + 2106 + relative * 7 + pt] * count)
        if len(indices) > ACTIVE:
            raise ValueError('too many non-king pieces')
        features[perspective, :len(indices)] = indices
    if board.turn:
        features = features[::-1].copy()
        material = -material
    return features, material


def canonicalize(features):
    """Map the existing full-king feature cache without decoding PSV again."""
    king=features//STRIDE;local=features%STRIDE
    file,rank=king//9,king%9
    square=local%81
    mirrored=(local//81)*81+(8-square//9)*9+square%9
    local=np.where((file>4)&(local<2106),mirrored,local)
    mapped=(rank*5+np.minimum(file,8-file))*STRIDE+local
    return np.where(features==INPUTS,SYMMETRIC_INPUTS,mapped).astype(np.int32)
