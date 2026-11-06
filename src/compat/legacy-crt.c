#define START "_start"
#include "crt_arch.h"
extern int main(int,char **,char **);
extern unsigned char __ehdr_start[];
void *__dso_handle = &__dso_handle;
extern int __libc_start_main(int (*)(),int,char **,void(*)(),void(*)(),void(*)());
/* Linux 1.2 provides no auxiliary vector to a static executable. */
void _start_c(long *p) {
    long argc=p[0], count=argc+2;
    while(p[count]) ++count;
    ++count;
    long stack[count+32];
    for(long i=0;i<count;++i) stack[i]=p[i];
    long *v=stack+count;
#define AUX(k,x) do { *v++=(k); *v++=(long)(x); } while(0)
    AUX(3,__ehdr_start+*(unsigned*)(__ehdr_start+28));
    AUX(4,32); AUX(5,*(unsigned short*)(__ehdr_start+44));
    AUX(6,4096); AUX(9,*(unsigned*)(__ehdr_start+24));
    AUX(11,0); AUX(12,0); AUX(13,0); AUX(14,0); AUX(0,0);
    __libc_start_main(main,argc,(char**)(stack+1),0,0,0);
}
