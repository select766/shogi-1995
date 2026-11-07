#define _DEFAULT_SOURCE
#define _POSIX_C_SOURCE 200809L
#include <sys/mount.h>
#include <unistd.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
int main(int argc,char **argv) {
    if(argc==2&&!strcmp(argv[1],"mount-proc")) { if(mount("proc","/proc","proc",0,0)<0) {perror("mount proc");return 1;}return 0; }
    if(argc==2&&!strcmp(argv[1],"sync")) {sync();return 0;}
    if(argc==3&&!strcmp(argv[1],"cat")) {
        int fd=open(argv[2],O_RDONLY);char b[4096];ssize_t n;
        if(fd<0){perror(argv[2]);return 1;}
        while((n=read(fd,b,sizeof(b)))>0) { ssize_t off=0;while(off<n) {ssize_t w=write(1,b+off,n-off);if(w<=0)return 1;off+=w;} }
        close(fd);return n<0;
    }
    return 2;
}
