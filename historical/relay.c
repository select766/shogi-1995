/* Host-controlled SIGINT relay, compiled with GCC 2.7.0/libc5.
 * Only __STOP__ is special. Normal lines are forwarded unchanged. */
#include <sys/types.h>
#include <sys/time.h>
#include <sys/wait.h>
#include <unistd.h>
#include <signal.h>
#include <string.h>
#include <errno.h>
#include <stdlib.h>
static int putall(int fd,char *b,int n){int k;while(n){k=write(fd,b,n);if(k<0){if(errno==EINTR)continue;return -1;}b+=k;n-=k;}return 0;}
int main(int argc,char **argv){int in[2],out[2],pid,n,i,len=0;char b[4096],line[4096];fd_set f;
 if(argc<2||pipe(in)||pipe(out))return 2;
 pid=fork();if(pid<0)return 2;
 if(!pid){dup2(in[0],0);dup2(out[1],1);dup2(out[1],2);close(in[0]);close(in[1]);close(out[0]);close(out[1]);execv(argv[1],argv+1);_exit(127);}
 close(in[0]);close(out[1]);
 for(;;){FD_ZERO(&f);FD_SET(0,&f);FD_SET(out[0],&f);if(select(out[0]+1,&f,0,0,0)<0){if(errno==EINTR)continue;break;}
  if(FD_ISSET(out[0],&f)){n=read(out[0],b,sizeof(b));if(n<=0)break;if(putall(1,b,n))break;}
  if(FD_ISSET(0,&f)){n=read(0,b,sizeof(b));if(n<=0)break;for(i=0;i<n;i++){
   if(len>=sizeof(line)-1)goto done;line[len++]=b[i];if(b[i]=='\n'){line[len]=0;if(!strcmp(line,"__STOP__\n"))kill(pid,SIGINT);else if(putall(in[1],line,len))goto done;len=0;}}}
 }
 done:kill(pid,SIGTERM);waitpid(pid,0,0);return 0;
}
