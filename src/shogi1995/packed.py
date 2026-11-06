"""Decode YaneuraOu PSV moves, whose flag bits differ from HCPE/Apery moves."""
def psv_move_usi(raw):
    destination=raw&127
    if destination>=81:raise ValueError('bad destination')
    def square(n):
        if not 0<=n<81:raise ValueError('bad source')
        return str(n//9+1)+chr(ord('a')+n%9)
    if raw&(1<<14):
        piece=(raw>>7)&127
        if not 1<=piece<=7:raise ValueError('bad dropped piece')
        return ' PLNSBRG'[piece]+'*'+square(destination)
    return square((raw>>7)&127)+square(destination)+('+' if raw&(1<<15) else '')
