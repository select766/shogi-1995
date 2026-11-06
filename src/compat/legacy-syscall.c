/* Restricted, single-thread runtime for Linux 1.2 i386; not a general libc port. */
typedef long L;
extern L shogi_raw_syscall(L,L,L,L,L,L,L);
#define RAW(n,a,b,c,d,e,f) shogi_raw_syscall(n,(L)(a),(L)(b),(L)(c),(L)(d),(L)(e),(L)(f))
struct tv32 { L sec, usec; };
struct vec { void *base; unsigned len; };
static L dispatch(L n,L a,L b,L c,L d,L e,L f) {
    if(n==192) { /* mmap2 -> Linux 1.2 mmap argument block */
        L args[]={a,b,c,d,e,f<<12};
        return RAW(90,args,0,0,0,0,0);
    }
    if(n==142) {
        L args[]={a,b,c,d,e};
        return RAW(82,args,0,0,0,0,0);
    }
    if(n==145 || n==146) { /* readv / writev */
        struct vec *v=(void*)b;
        L done=0;
        for(L i=0;i<c;++i) {
            L r=RAW(n==145?3:4,a,v[i].base,v[i].len,0,0,0);
            if(r<0) return done?done:r;
            done+=r;
            if((unsigned)r<v[i].len) break;
        }
        return done;
    }
    if(n==265 || n==403) { /* clock_gettime -> fixed guest wall clock */
        if(a!=0 && a!=1) return -22;
        struct tv32 t;
        L r=RAW(78,&t,0,0,0,0,0);
        if(r<0) return r;
        if(n==403) { long long *v=(void*)b; v[0]=t.sec; v[1]=t.usec*1000LL; }
        else { L *v=(void*)b; v[0]=t.sec; v[1]=t.usec*1000; }
        return 0;
    }
    if(n==162) { /* nanosleep -> old select */
        L *v=(void*)a;
        struct tv32 t={v[0],(v[1]+999)/1000};
        L args[]={0,0,0,0,(L)&t};
        return RAW(82,args,0,0,0,0,0);
    }
    if(n==175) return RAW(126,a,b,c,0,0,0); /* 32-bit signal mask */
    if(n==238) return RAW(37,a,b,0,0,0,0); /* main-thread signal */
    if(n==174) {
        L old[4], action[4], *p=(void*)b;
        if(p) { action[0]=p[0]; action[1]=p[3]; action[2]=p[1]; action[3]=p[2]; }
        L r=RAW(67,a,p?action:0,c?old:0,0,0,0);
        if(r==0 && c) { p=(void*)c; p[0]=old[0]; p[1]=old[2]; p[2]=old[3]; p[3]=old[1]; p[4]=0; }
        return r;
    }
    if(n==258) return RAW(20,0,0,0,0,0,0); /* main thread ID */
    if(n==252) return RAW(1,a,0,0,0,0,0); /* process exit */
    if(n==240 || n==422) return -38; /* No OS threads supported. */
    return RAW(n,a,b,c,d,e,f);
}

L shogi_legacy_syscall(L n,L a,L b,L c,L d,L e,L f) {
    L r=dispatch(n,a,b,c,d,e,f);
#ifdef SHOGI1995_SYSCALL_TRACE
    if(r<0 && r>=-4095) {
        char buf[64],digits[16]; int k=0,j=0; L x=n;
        buf[k++]='S'; buf[k++]='Y'; buf[k++]='S'; buf[k++]=' ';
        do {digits[j++]=(char)('0'+x%10);x/=10;}while(x);
        while(j)buf[k++]=digits[--j];
        buf[k++]=' ';buf[k++]='-'; x=-r;
        do {digits[j++]=(char)('0'+x%10);x/=10;}while(x);
        while(j)buf[k++]=digits[--j];
        buf[k++]='\n'; RAW(4,2,buf,k,0,0,0);
    }
#endif
    return r;
}

int __set_thread_area(void *base) {
    /* Linux 1.2 limits an LDT segment to the user address range. */
    unsigned desc[]={0,(unsigned)base,(0xbfffffffU-(unsigned)base)>>12,0x51};
    L r=RAW(123,1,desc,16,0,0,0);
    if(r<0) return r;
    __asm__ volatile("movw %0,%%gs" : : "r"((unsigned short)7) : "memory");
    return 1; /* musl: TLS works, but native threading is unavailable */
}
