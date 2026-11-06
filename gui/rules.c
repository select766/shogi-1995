#include "rules.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
static const char *letters=" PLNSGBRK";
static int side(int v) { return v<0; }
static int base(int v) { v=abs(v); return v>8?v-8:v; }
void initial(Position *p) {
    static const int back[]={2,3,4,5,8,5,4,3,2};
    int x; memset(p,0,sizeof(*p));
    for(x=0;x<9;x++) { p->b[x]=-back[x]; p->b[72+x]=back[x]; p->b[18+x]=-1; p->b[54+x]=1; }
    p->b[10]=-7; p->b[16]=-6; p->b[64]=6; p->b[70]=7;
}
static int attacks(const Position *p,int a,int b) {
    int v=abs(p->b[a]), dx=b%9-a%9, dy=b/9-a/9, sx,sy,i,j;
    if(p->b[a]<0) { dx=-dx; dy=-dy; }
    if(!dx&&!dy) return 0;
    if(v==1) return dx==0&&dy==-1;
    if(v==3) return abs(dx)==1&&dy==-2;
    if(v==4) return (dy==-1&&abs(dx)<=1)||(dy==1&&abs(dx)==1);
    if(v==5||(v>=9&&v<=12)) return (dy==-1&&abs(dx)<=1)||(dy==0&&abs(dx)==1)||(dy==1&&dx==0);
    if(v==8) return abs(dx)<=1&&abs(dy)<=1;
    if(v==14&&abs(dx)+abs(dy)==1) return 1;
    if(v==15&&abs(dx)==1&&abs(dy)==1) return 1;
    if(!((v==2&&dx==0&&dy<0)||((v==6||v==14)&&abs(dx)==abs(dy))||((v==7||v==15)&&(!dx||!dy)))) return 0;
    sx=(b%9>a%9)-(b%9<a%9); sy=(b/9>a/9)-(b/9<a/9);
    for(i=a%9+sx,j=a/9+sy;i!=b%9||j!=b/9;i+=sx,j+=sy) if(p->b[j*9+i]) return 0;
    return 1;
}
int in_check(const Position *p,int s) {
    int i,k=-1;
    for(i=0;i<81;i++) if(p->b[i]==(s?-8:8)) k=i;
    if(k<0) return 1;
    for(i=0;i<81;i++) if(p->b[i]&&side(p->b[i])!=s&&attacks(p,i,k)) return 1;
    return 0;
}
int parse_move(const char *s, Move *m) {
    size_t n=strlen(s); const char *c;
    memset(m,0,sizeof(*m)); m->from=-1;
    if(n==4&&s[1]=='*') {
        c=strchr(letters,s[0]); if(!c||c==letters||c-letters>7) return 0;
        m->drop=c-letters;
    } else {
        if((n!=4&&n!=5)||s[0]<'1'||s[0]>'9'||s[1]<'a'||s[1]>'i'||(n==5&&s[4]!='+')) return 0;
        m->from=(s[1]-'a')*9+9-(s[0]-'0'); m->promote=n==5;
    }
    if(s[2]<'1'||s[2]>'9'||s[3]<'a'||s[3]>'i') return 0;
    m->to=(s[3]-'a')*9+9-(s[2]-'0'); return 1;
}
void move_text(Move m,char *s) {
    if(m.drop) sprintf(s,"%c*%d%c",letters[m.drop],9-m.to%9,'a'+m.to/9);
    else sprintf(s,"%d%c%d%c%s",9-m.from%9,'a'+m.from/9,9-m.to%9,'a'+m.to/9,m.promote?"+":"");
}
void apply(Position *p,Move m) {
    int v=m.drop?m.drop:abs(p->b[m.from]);
    if(p->b[m.to]) p->h[p->turn][base(p->b[m.to])]++;
    if(m.drop) p->h[p->turn][m.drop]--; else p->b[m.from]=0;
    p->b[m.to]=(p->turn?-1:1)*(v+(m.promote?8:0)); p->turn^=1;
}
static int board_escape(const Position *p);
int legal(const Position *p,Move m) {
    int v,r,i; Position q;
    if(m.to<0||m.to>=81||m.from>=81||m.promote<0||m.promote>1) return 0;
    if(p->b[m.to]&&(side(p->b[m.to])==p->turn||abs(p->b[m.to])==8)) return 0;
    r=p->turn?8-m.to/9:m.to/9;
    if(m.drop) {
        if(m.drop<1||m.drop>7||m.promote||p->b[m.to]||!p->h[p->turn][m.drop]) return 0;
        if((m.drop<=2&&r==0)||(m.drop==3&&r<=1)) return 0;
        if(m.drop==1) for(i=m.to%9;i<81;i+=9) if(p->b[i]==(p->turn?-1:1)) return 0;
    } else {
        if(m.from<0||!p->b[m.from]||side(p->b[m.from])!=p->turn||!attacks(p,m.from,m.to)) return 0;
        v=abs(p->b[m.from]);
        if(m.promote) {
            if(v>7||v==5||((p->turn?8-m.from/9:m.from/9)>2&&r>2)) return 0;
        } else if((v<=2&&r==0)||(v==3&&r<=1)) return 0;
    }
    q=*p; apply(&q,m); if(in_check(&q,p->turn)) return 0;
    /* A checking pawn drop can only be answered by a board move (adjacent check). */
    if(m.drop==1) {
        int king=m.to+(p->turn?9:-9);
        if(king>=0&&king<81&&q.b[king]==(p->turn?8:-8)&&!board_escape(&q)) return 0;
    }
    return 1;
}
static int board_escape(const Position *p) {
    int a,b,c; Move m;
    for(a=0;a<81;a++) if(p->b[a]&&side(p->b[a])==p->turn)
        for(b=0;b<81;b++) for(c=0;c<2;c++) { m=(Move){a,b,c,0}; if(legal(p,m)) return 1; }
    return 0;
}
int has_legal(const Position *p) {
    int v,b; Move m;
    if(board_escape(p)) return 1;
    for(v=1;v<=7;v++) if(p->h[p->turn][v]) for(b=0;b<81;b++) { m=(Move){-1,b,0,v}; if(legal(p,m)) return 1; }
    return 0;
}
int declaration(const Position *p) {
    int i,v,n=0,points=0,k=-1,s=p->turn;
    if(in_check(p,s)) return 0;
    for(i=0;i<81;i++) if(p->b[i]&&side(p->b[i])==s) {
        v=base(p->b[i]); if(v==8) k=i;
        else if((s?8-i/9:i/9)<=2) { n++; points+=(v==6||v==7)?5:1; }
    }
    for(v=1;v<=7;v++) points+=p->h[s][v]*((v==6||v==7)?5:1);
    return k>=0&&(s?8-k/9:k/9)<=2&&n>=10&&points>=(s?27:28);
}
int read_sfen(Position *p,const char *s) {
    Position q; int x=0,y=0,pro=0,sign,n=0,v,k[2]={0,0}; const char *c;
    memset(&q,0,sizeof(q));
    while(*s&&*s!=' ') {
        if(*s=='/') { if(x!=9||++y>8) return 0; x=0; s++; continue; }
        if(*s=='+') { if(pro) return 0; pro=8; s++; continue; }
        if(*s>='1'&&*s<='9') { if(pro) return 0; x+=*s++-'0'; if(x>9) return 0; continue; }
        sign=(*s>='a'&&*s<='z'); c=strchr(letters,sign?*s-32:*s);
        if(!c||c==letters||x>=9) return 0; v=c-letters;
        if(pro&&(v==5||v==8)) return 0;
        q.b[y*9+x++]=(sign?-1:1)*(v+pro); if(v==8) k[sign]++; pro=0; s++;
    }
    if(x!=9||y!=8||pro||k[0]!=1||k[1]!=1||*s++!=' ') return 0;
    if(*s!='b'&&*s!='w') return 0; q.turn=*s++=='w'; if(*s++!=' ') return 0;
    if(*s=='-') s++;
    else while(*s&&*s!=' ') {
        if(*s>='0'&&*s<='9') { n=n*10+*s++-'0'; if(n>18) return 0; continue; }
        sign=(*s>='a'&&*s<='z'); c=strchr(letters,sign?*s-32:*s);
        if(!c||c==letters||c-letters>7) return 0;
        q.h[sign][c-letters]+=n?n:1; n=0; s++;
    }
    if(n) return 0; *p=q; return 1;
}
