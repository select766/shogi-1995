#!/usr/bin/env python3
"""Generate XBM text for pre-Unicode Tk 4. Runtime needs no Pillow/fonts."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
out = Path(__file__).parent / 'assets'
font_path = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
labels = {
 'title':'将棋 1995', 'settings':'対局設定', 'sente':'先手', 'gote':'後手',
 'human':'人間', 'ai':'AI', 'time':'持ち時間（分）', 'increment':'１手ごとの加算（秒）',
 'start':'対局開始', 'next':'次の対局', 'resign':'投了', 'declare':'入玉宣言',
 'record':'棋譜', 'promote_question':'成りますか？', 'yes':'成る', 'no':'成らない',
 'choose':'駒と移動先をクリックしてください', 'thinking':'AI 思考中',
 'starting':'エンジン準備中', 'playing':'対局中', 'check':'王手',
 'finished':'終局', 'illegal':'そこには指せません', 'failure':'エンジン接続エラー（ログを確認）',
 'draw':'千日手・引き分け', 'sente_win':'先手の勝ち', 'gote_win':'後手の勝ち',
 'perpetual':'連続王手の千日手', 'drop':'打', 'promoted':'成', 'unpromoted':'不成',
 'side0':'▲', 'side1':'△', 'help':'持ち時間を超えても対局は続きます',
 'credit':'Linux / Tcl・Tk   音声なし', 'blackhand':'先手の持ち駒', 'whitehand':'後手の持ち駒',
 'none':'なし', 'cancel':'キャンセル',
}
for i,t in enumerate(['','歩','香','桂','銀','金','角','飛','玉','と','成香','成桂','成銀','','馬','龍']):
 if t: labels['name'+str(i)]=t
for i,t in enumerate('一二三四五六七八九',1): labels['rank'+str(i)]=t

def bitmap(name,text,size=16,rotate=False,cell=False):
 font=ImageFont.truetype(font_path,size,index=0)
 width=34 if cell else int(font.getlength(text))+4
 im=Image.new('1',(width,34 if cell else size+8),0)
 d=ImageDraw.Draw(im);box=d.textbbox((0,0),text,font=font)
 x=(width-(box[2]-box[0]))//2-box[0]; y=(im.height-(box[3]-box[1]))//2-box[1]
 d.text((x,y),text,font=font,fill=1)
 if rotate: im=im.rotate(180)
 im.save(out/(name+'.xbm'))
for name,t in labels.items(): bitmap(name,t,18 if name in ['title','settings'] else 15)
for i,t in enumerate(['','歩','香','桂','銀','金','角','飛','玉','と','杏','圭','全','','馬','龍']):
 if t:
  for side in range(2): bitmap('piece%d_%d'%(i,side),t,25,bool(side),True)
