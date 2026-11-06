/* Minimal PID 1 for the Slackware 3.0 compatibility probe. No host libc. */
typedef unsigned int u32;
/* Linux 1.2's ELF loader writes padding in the final load segment. */
static volatile int loader_padding = 1;
static int call(int n, int a, int b, int c) {
    int r;
    __asm__ volatile("int $0x80" : "=a"(r) : "a"(n), "b"(a), "c"(b), "d"(c) : "memory");
    return r;
}
static void message(const char *s) {
    int n=0; while(s[n]) ++n;
    call(4,1,(int)s,n);
}
void guest_main(void) {
    loader_padding = 0;
    int fd=call(5,(int)"/dev/ttyS0",2|0x100|0x800,0);
    if(fd<0) for(;;) {}
    struct { u32 in,out,control,local; unsigned char line,cc[19]; } t;
    if(call(54,fd,0x5401,(int)&t)==0) {
        t.in=0; t.out=0; t.local=0; t.control=0x18b2;
        t.cc[5]=0; t.cc[6]=1;
        call(54,fd,0x5402,(int)&t);
    }
    call(55,fd,4,2);
    for(int i=0;i<3;++i) call(63,fd,i,0);
    message("SHOGI1995 guest init ready\n");
    for(;;) {
        int pid=call(2,0,0,0);
        if(pid==0) {
#ifdef SHOGI1995_ENGINE_INIT
            char *args[]={"/shogi",0};
#else
            char *args[]={"/bin/bash",0};
#endif
            char *env[]={"PATH=/bin:/sbin:/usr/bin","TERM=vt100","PS1=guest1995# ",0};
            call(11,(int)args[0],(int)args,(int)env);
            message("exec bash failed\n"); call(1,127,0,0);
        }
        if(pid<0) { message("fork failed\n"); for(;;) {} }
        call(7,-1,0,0);
        message("guest shell exited; restart VM to retry\n");
        for(;;) call(29,0,0,0);
    }
}
__asm__(".global _start\n_start: call guest_main\n1: jmp 1b\n");
