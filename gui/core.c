#define _POSIX_C_SOURCE 200809L
#include "rules.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/time.h>
#include <sys/select.h>
#include <sys/wait.h>
#include <signal.h>
#include <fcntl.h>
#include <errno.h>
#include <stdarg.h>
static Position pos,history[MAX_PLY+1];
static int checks[MAX_PLY+1],players[2],ply,active,debug_mode,engine_state,engine_in=-1,engine_out=-1;
static int match_byoyomi_ms, match_max_ply;
static pid_t engine_pid=-1;
static double remaining[2],increment,last_tick,deadline;
static char moves[MAX_PLY][8],result[96]="settings",engine_path[1024]="/shogi",engine_dir[1024]="/";
static char options[64][512]; static int option_count;
static char queue[65536]; static size_t queued, ne;
static FILE *logfile;
static double now(void) { struct timeval t; gettimeofday(&t,0); return t.tv_sec+t.tv_usec/1000000.0; }
static void logline(const char *tag,const char *line) { if(logfile) { fprintf(logfile,"%.3f %s %s\n",now(),tag,line); fflush(logfile); } }
static void emit(const char *fmt,...) { char s[8192]; va_list ap; va_start(ap,fmt); vsnprintf(s,sizeof(s),fmt,ap); va_end(ap); puts(s); fflush(stdout); logline("UI<",s); }
static void send_engine(const char *s) {
    size_t n=strlen(s); logline("USI>",s);
    if(queued+n+1>=sizeof(queue)) { strcpy(result,"engine_write_overflow"); active=0; return; }
    memcpy(queue+queued,s,n); queued+=n; queue[queued++]='\n';
}
static void engine_close(void) {
    if(engine_in>=0) close(engine_in); if(engine_out>=0) close(engine_out);
    engine_in=engine_out=-1; queued=0; ne=0;
    if(engine_pid>0) { kill(engine_pid,SIGKILL); while(waitpid(engine_pid,0,0)<0&&errno==EINTR) {} }
    engine_pid=-1; engine_state=0;
}
static void snapshot(void) {
    char board[400]="",hands[140]="",t[24]; int i,s;
    for(i=0;i<81;i++) { sprintf(t,"%s%d",i?",":"",pos.b[i]); strcat(board,t); }
    for(s=0;s<2;s++) for(i=1;i<=7;i++) { sprintf(t,"%s%d",s||i>1?",":"",pos.h[s][i]); strcat(hands,t); }
    emit("state %d %d %d %.0f %.0f %s %s %s %d %d %d",pos.turn,active,declaration(&pos),remaining[0]*1000,remaining[1]*1000,board,hands,result,players[0],players[1],ply);
}
static void tick(void) { double t=now(); if(active&&engine_state!=1&&engine_state!=2) remaining[pos.turn]-=t-last_tick; last_tick=t; }
static void finish(const char *s) {
    tick(); active=0; snprintf(result,sizeof(result),"%s",s);
    if(engine_pid>0) {
        send_engine("stop"); send_engine("gameover draw"); send_engine("quit");
        engine_state=5; deadline=now()+1;
    } else engine_close();
    /* New games reap this engine before spawning another. Stale bestmove is ignored. */
    snapshot();
}
static void fail(const char *s) { emit("error %s",s); engine_close(); finish(s); }
static void think(void) {
    char command[20000],t[160]; int i;
    if(!active||!players[pos.turn]||engine_state!=3) return;
    strcpy(command,"position startpos");
    if(ply) { strcat(command," moves"); for(i=0;i<ply;i++) { strcat(command," "); strcat(command,moves[i]); } }
    send_engine(command);
    if(match_byoyomi_ms) snprintf(t,sizeof(t),"go btime 0 wtime 0 byoyomi %d",match_byoyomi_ms);
    else snprintf(t,sizeof(t),"go btime %.0f wtime %.0f binc %.0f winc %.0f",remaining[0]>0?remaining[0]*1000:0,remaining[1]>0?remaining[1]*1000:0,increment*1000,increment*1000);
    send_engine(t); engine_state=4;
}
static void accept(Move m) {
    int mover=pos.turn,v=m.drop?m.drop:abs(pos.b[m.from]),i,n=0,start=0,loser=-1,s,all;
    char text[8],r[96];
    tick(); move_text(m,text); strcpy(moves[ply],text);
    emit("move %d %d %d %d %d %d %d %d %d %s",ply+1,mover,9-m.to%9,m.to/9+1,v,m.promote,m.drop,m.from<0?0:9-m.from%9,m.from<0?0:m.from/9+1,text);
    apply(&pos,m); remaining[mover]+=increment; if(match_byoyomi_ms) remaining[pos.turn]=match_byoyomi_ms/1000.0; ply++;
    history[ply]=pos; checks[ply]=in_check(&pos,pos.turn); strcpy(result,checks[ply]?"check":"playing");
    for(i=0;i<=ply;i++) if(memcmp(&history[i],&pos,sizeof(pos))==0) { if(!n) start=i; n++; }
    if(n>=4) {
        for(s=0;s<2;s++) { all=1; for(i=start+1;i<=ply;i++) if((history[i-1].turn==s)&&!checks[i]) all=0; if(all) loser=s; }
        if(loser>=0) { sprintf(r,"%s_loses_perpetual_check",loser?"gote":"sente"); finish(r); }
        else finish("draw_repetition"); return;
    }
    if(!has_legal(&pos)) { sprintf(r,"%s_wins_mate",mover?"gote":"sente"); finish(r); return; }
    if(ply>=MAX_PLY || (match_max_ply && ply>=match_max_ply)) { finish("draw_move_limit"); return; }
    last_tick=now(); snapshot(); think();
}
#ifdef SHOGI_GUI_LEGACY
/* Linux 1.2 predates ELF TLS. Avoid musl's post-fork TLS bookkeeping in the
 * child and clear GS before exec, as a libc5 parent does. The GUI is single-threaded. */
extern char **environ;
static int raw3(int n,int a,int b,int c) {
    int r; __asm__ volatile("int $0x80":"=a"(r):"a"(n),"b"(a),"c"(b),"d"(c):"memory");return r;
}
#endif
static void spawn_engine(void) {
    int a[2],b[2];
    if(pipe(a)<0) { fail("engine_pipe_failed"); return; }
    if(pipe(b)<0) { close(a[0]);close(a[1]);fail("engine_pipe_failed");return; }
#ifdef SHOGI_GUI_LEGACY
    engine_pid=raw3(2,0,0,0);
    if(engine_pid==0) {
        char *args[]={engine_path,0};
        raw3(63,a[0],0,0);raw3(63,b[1],1,0);
        raw3(6,a[0],0,0);raw3(6,a[1],0,0);raw3(6,b[0],0,0);raw3(6,b[1],0,0);
        if(raw3(12,(int)engine_dir,0,0)<0) raw3(1,126,0,0);
        __asm__ volatile("movw %0,%%gs"::"r"((unsigned short)0):"memory");
        raw3(11,(int)engine_path,(int)args,(int)environ);raw3(1,127,0,0);
        for(;;) {}
    }
#else
    engine_pid=fork();
    if(engine_pid==0) {
        dup2(a[0],0); dup2(b[1],1); close(a[0]);close(a[1]);close(b[0]);close(b[1]);
        if(chdir(engine_dir)<0) { perror(engine_dir); _exit(126); }
        execl(engine_path,engine_path,(char*)0); perror(engine_path); _exit(127);
    }
#endif
    close(a[0]);close(b[1]);
    if(engine_pid<0) { close(a[1]);close(b[0]); fail("engine_fork_failed");return; }
    { char message[64]; sprintf(message,"spawn pid=%ld",(long)engine_pid); logline("ENGINE",message); }
    engine_in=a[1]; engine_out=b[0];
    fcntl(engine_in,F_SETFL,O_NONBLOCK); fcntl(engine_out,F_SETFL,O_NONBLOCK);
    engine_state=1; deadline=now()+120; send_engine("usi");
}
static void engine_line(char *s) {
    char *t; int i; Move m;
    logline("USI<",s);
    if(engine_state==1&&!strcmp(s,"usiok")) {
        for(i=0;i<option_count;i++) { char command[1100],*eq=strchr(options[i],'='); if(!eq) continue; *eq=0; snprintf(command,sizeof(command),"setoption name %.511s value %.511s",options[i],eq+1); *eq='='; send_engine(command); }
        send_engine("isready"); engine_state=2; deadline=now()+120;
    } else if(engine_state==2&&!strcmp(s,"readyok")) {
        send_engine("usinewgame"); engine_state=3; last_tick=now(); strcpy(result,"playing"); snapshot(); think();
    } else if(engine_state==4&&!strncmp(s,"bestmove ",9)) {
        engine_state=3; t=s+9; t[strcspn(t," \r\t")]=0;
        if(!strcmp(t,"resign")) { char r[64]; sprintf(r,"%s_wins_resignation",pos.turn?"sente":"gote"); finish(r); }
        else if(!strcmp(t,"win")) {
            if(declaration(&pos)) finish(pos.turn?"gote_wins_declaration":"sente_wins_declaration");
            else fail("engine_invalid_declaration");
        } else if(parse_move(t,&m)&&legal(&pos,m)) accept(m);
        else fail("engine_illegal_move");
    }
}
static char *trim(char *s) { char *e; while(*s==' '||*s=='\t') s++; e=s+strlen(s); while(e>s&&(e[-1]=='\r'||e[-1]=='\n'||e[-1]==' '||e[-1]=='\t')) *--e=0; return s; }
static int load_config(const char *name) {
    char line[2048],*s,*e,*key; FILE *f=fopen(name,"r");
    if(!f) { fprintf(stderr,"Cannot read config: %s\n",name); return 0; }
    while(fgets(line,sizeof(line),f)) {
        s=trim(line); if(!*s||*s=='#') continue; e=strchr(s,'='); if(!e) { fclose(f); return 0; }
        *e=0; key=trim(s); s=trim(e+1);
        if(!strcmp(key,"Engine")) snprintf(engine_path,sizeof(engine_path),"%s",s);
        else if(!strcmp(key,"EngineDir")) snprintf(engine_dir,sizeof(engine_dir),"%s",s);
        else if(!strcmp(key,"MatchByoyomiMs")) { match_byoyomi_ms=atoi(s); if(match_byoyomi_ms<0 || match_byoyomi_ms>3600000) { fclose(f); return 0; } }
        else if(!strcmp(key,"MatchMaxPly")) { match_max_ply=atoi(s); if(match_max_ply<0 || match_max_ply>MAX_PLY) { fclose(f); return 0; } }
        else if(option_count<64&&strlen(key)+strlen(s)+2<sizeof(options[0])) snprintf(options[option_count++],sizeof(options[0]),"%s=%s",key,s);
        else { fclose(f); return 0; }
    }
    fclose(f); return engine_path[0]=='/'&&engine_dir[0]=='/';
}
static int command(char *s) {
    Move m; char a[32],b[32],tail; double t,inc; int i,j; logline("UI>",s);
    if(!strcmp(s,"close")) return 0;
    if(sscanf(s,"new %31s %31s %lf %lf %c",a,b,&t,&inc,&tail)==4) {
        if((strcmp(a,"human")&&strcmp(a,"ai"))||(strcmp(b,"human")&&strcmp(b,"ai"))||!(t>=0&&t<=86400)||!(inc>=0&&inc<=3600)) { emit("error invalid_settings"); return 1; }
        engine_close(); initial(&pos); ply=0; memset(checks,0,sizeof(checks)); history[0]=pos;
        players[0]=!strcmp(a,"ai");players[1]=!strcmp(b,"ai"); remaining[0]=remaining[1]=match_byoyomi_ms ? match_byoyomi_ms/1000.0 : t; increment=inc; active=1; last_tick=now(); strcpy(result,"playing"); emit("reset");
        if(players[0]||players[1]) { strcpy(result,"engine_starting"); spawn_engine(); }
        snapshot();
    } else if(!strncmp(s,"move ",5)) {
        if(active&&!players[pos.turn]&&engine_state!=1&&engine_state!=2&&parse_move(s+5,&m)&&legal(&pos,m)) accept(m); else emit("error illegal_move");
    } else if(!strcmp(s,"action")) {
        if(active) {
            if(declaration(&pos)) finish(pos.turn?"gote_wins_declaration":"sente_wins_declaration");
            else finish(pos.turn?"sente_wins_resignation":"gote_wins_resignation");
        }
    } else if(!strncmp(s,"targets ",8)) {
        int from,drop; char list[4096]="",v[16];
        if(sscanf(s+8,"%d %d",&from,&drop)==2&&active&&!players[pos.turn]) {
            for(i=0;i<81;i++) for(j=0;j<2;j++) { m=(Move){from,i,j,drop}; if(legal(&pos,m)) { move_text(m,v); strcat(list," ");strcat(list,v); } }
        }
        emit("targets%s",list);
    } else if(!strcmp(s,"state")) snapshot();
    else if(debug_mode&&!strncmp(s,"sfen ",5)) {
        if(players[0]||players[1]) emit("error sfen_requires_human_game");
        else if(read_sfen(&pos,s+5)) { ply=0;history[0]=pos;emit("reset"); snapshot(); } else emit("error invalid_sfen");
    } else if(debug_mode&&!strcmp(s,"legal")) {
        char v[16];
        for(i=0;i<81;i++) for(j=0;j<81;j++) { int pro;for(pro=0;pro<2;pro++) { m=(Move){i,j,pro,0}; if(legal(&pos,m)) { move_text(m,v); emit("legal %s",v); } } }
        for(i=1;i<=7;i++) for(j=0;j<81;j++) { m=(Move){-1,j,0,i}; if(legal(&pos,m)) { move_text(m,v); emit("legal %s",v); } } emit("legal_end");
    } else emit("error unknown_command");
    return 1;
}
int main(int argc,char **argv) {
    char input[4096],eng[8192],buf[4096]; size_t ni=0; int running=1,i;
    for(i=1;i<argc;i++) {
        if(!strcmp(argv[i],"--debug")) debug_mode=1;
        else if(!strcmp(argv[i],"--config")&&i+1<argc) { if(!load_config(argv[++i])) return 2; }
        else if(!strcmp(argv[i],"--log")&&i+1<argc) { logfile=fopen(argv[++i],"a"); if(!logfile) return 2; }
        else return 2;
    }
    signal(SIGPIPE,SIG_IGN); initial(&pos); last_tick=now(); emit("ready");
    while(running) {
        fd_set rd,wr; struct timeval timeout={0,100000}; int max=0,n,fd,eout=engine_out;
        tick(); FD_ZERO(&rd); FD_ZERO(&wr); FD_SET(0,&rd);
        if(engine_out>=0) { FD_SET(engine_out,&rd); max=engine_out; }
        if(engine_in>=0&&queued) { FD_SET(engine_in,&wr); if(engine_in>max) max=engine_in; }
        n=select(max+1,&rd,&wr,0,&timeout);
        if(n<0&&errno!=EINTR) break;
        if(n>0) {
            if(engine_in>=0&&FD_ISSET(engine_in,&wr)) {
                ssize_t count=write(engine_in,queue,queued);
                if(count>0) { memmove(queue,queue+count,queued-count);queued-=count; }
                else if(count<0&&errno!=EAGAIN&&errno!=EINTR) fail("engine_write_failed");
            }
            /* Process engine data before UI commands, which may close/reuse its descriptors. */
            if(eout>=0&&eout==engine_out&&FD_ISSET(eout,&rd)) {
                ssize_t count=read(eout,buf,sizeof(buf));
                if(count==0 && engine_state==5) { engine_close(); ne=0; }
                else if(count==0) {
                    int status; char detail[100];
                    if(waitpid(engine_pid,&status,WNOHANG)==engine_pid) {
                        snprintf(detail,sizeof(detail),"exit status=%d signal=%d",WIFEXITED(status)?WEXITSTATUS(status):-1,WIFSIGNALED(status)?WTERMSIG(status):0);
                        logline("ENGINE",detail); engine_pid=-1;
                    }
                    fail("engine_disconnected"); ne=0;
                }
                else if(count>0) for(fd=0;fd<count;fd++) {
                    if(buf[fd]=='\n') { eng[ne]=0; if(ne&&eng[ne-1]=='\r') eng[--ne]=0;engine_line(eng);ne=0; }
                    else if(ne+1<sizeof(eng)) eng[ne++]=buf[fd];
                    else { fail("engine_line_too_long");ne=0;break; }
                    if(engine_out!=eout) { ne=0; break; }
                }
            }
            if(FD_ISSET(0,&rd)) {
                ssize_t count=read(0,buf,sizeof(buf)); if(count<=0) break;
                for(fd=0;fd<count&&running;fd++) {
                    if(buf[fd]=='\n') { input[ni]=0; running=command(trim(input));ni=0; }
                    else if(ni+1<sizeof(input)) input[ni++]=buf[fd]; else { running=0; break; }
                }
            }
        }
        if((engine_state==1||engine_state==2)&&now()>deadline) fail("engine_handshake_timeout");
        if(engine_state==5&&now()>deadline) engine_close();
        if(active) { static double refresh=0; if(now()-refresh>=0.5) { snapshot(); refresh=now(); } }
    }
    engine_close(); if(logfile) fclose(logfile); return 0;
}
