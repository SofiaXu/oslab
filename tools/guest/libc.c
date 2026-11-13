/* Small teaching runtime for Linux 0.11's int 0x80 and ZMAGIC ABI.
 * Deliberately NOT a full libc: unbuffered I/O, integers only in printf,
 * bounded bump allocator. Native Ubuntu programs use the real system libc. */
#include <unistd.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <signal.h>
#include <sys/wait.h>
#include <sys/times.h>
#include <sys/stat.h>
#include <time.h>

int errno;
static long call3(int n, long a, long b, long c)
{
    long r;
    __asm__ volatile("int $0x80" : "=a"(r) : "0"(n), "b"(a), "c"(b), "d"(c) : "memory", "cc");
    if (r < 0) { errno = -r; return -1; }
    return r;
}
int read(int f, void *p, unsigned n) { return call3(3,f,(long)p,n); }
int write(int f, const void *p, unsigned n) { return call3(4,f,(long)p,n); }
int close(int f) { return call3(6,f,0,0); }
int open(const char *p, int f, ...) {
    va_list a; int m=0;
    if (f & O_CREAT) { va_start(a,f); m=va_arg(a,int); va_end(a); }
    return call3(5,(long)p,f,m);
}
off_t lseek(int f, off_t off, int whence) { return call3(19,f,off,whence); }
pid_t fork(void) { return call3(2,0,0,0); }
pid_t getpid(void) { return call3(20,0,0,0); }
pid_t getppid(void) { return call3(64,0,0,0); }
pid_t waitpid(pid_t p,int *status,int options) { return call3(7,p,(long)status,options); }
pid_t wait(int *status) { return waitpid(-1,status,0); }
int pipe(int *p) { return call3(42,(long)p,0,0); }
int dup(int f) { return call3(41,f,0,0); }
int dup2(int f,int g) { return call3(63,f,g,0); }
int unlink(const char *p) { return call3(10,(long)p,0,0); }
int chdir(const char *p) { return call3(12,(long)p,0,0); }
int execve(const char *p,char *const a[],char *const e[]) { return call3(11,(long)p,(long)a,(long)e); }
int mkdir(const char *p,mode_t mode) { return call3(39,(long)p,mode,0); }
int stat(const char *p,struct stat *s) { return call3(18,(long)p,(long)s,0); }
int fstat(int f,struct stat *s) { return call3(28,f,(long)s,0); }
int chmod(const char *p,mode_t m) { return call3(15,(long)p,m,0); }
int kill(pid_t p,int s) { return call3(37,p,s,0); }
int pause(void) { return call3(29,0,0,0); }
unsigned alarm(unsigned n) { return call3(27,n,0,0); }
void sync(void) { call3(36,0,0,0); }
clock_t times(struct tms *t) { return call3(43,(long)t,0,0); }
time_t time(time_t *t) { return call3(13,(long)t,0,0); }
clock_t clock(void) { struct tms t; times(&t); return t.tms_utime+t.tms_stime; }
long syscall(long n,...) {
    va_list ap; long a,b,c;
    va_start(ap,n); a=va_arg(ap,long); b=va_arg(ap,long); c=va_arg(ap,long); va_end(ap);
    return call3(n,a,b,c);
}
void _exit(int n) { call3(1,n,0,0); for (;;) {} }
void exit(int n) { _exit(n); }
void abort(void) { kill(getpid(),SIGABRT); _exit(134); }

/* Historical sys_signal passes the restorer as the third register argument.
 * Handler receives signo above the return address, followed by saved registers.
 * This restorer mirrors Linux 0.11 kernel/signal.c's SA_NOMASK frame. */
__asm__(".text\n.globl __restore\n__restore:\naddl $4,%esp\npopl %eax\npopl %ecx\npopl %edx\npopfl\nret\n");
extern void __restore(void);
void (*signal(int n,void (*fn)(int)))(int) { return (void (*)(int))call3(48,n,(long)fn,(long)__restore); }
static void alarm_handler(int n) { (void)n; }
unsigned sleep(unsigned n) {
    void (*old)(int); unsigned previous;
    if (!n) return 0;
    old=signal(SIGALRM,alarm_handler); previous=alarm(n); pause(); n=alarm(0);
    signal(SIGALRM,old); if(previous) alarm(previous); return n;
}
int usleep(unsigned n) { return sleep((n+999999U)/1000000U); }

size_t strlen(const char *s) { const char *p=s; while(*p)++p; return p-s; }
int strcmp(const char *a,const char *b) { while(*a && *a==*b){++a;++b;} return (unsigned char)*a-(unsigned char)*b; }
int strncmp(const char *a,const char *b,size_t n) { while(n && *a && *a==*b){++a;++b;--n;} return n ? (unsigned char)*a-(unsigned char)*b:0; }
char *strcpy(char *d,const char *s) { char *r=d; while((*d++=*s++)); return r; }
char *strncpy(char *d,const char *s,size_t n) { size_t i; for(i=0;i<n;++i)d[i]=*s ? *s++:0; return d; }
char *strcat(char *d,const char *s) { strcpy(d+strlen(d),s); return d; }
char *strchr(const char *s,int c) { do {if(*s==c)return (char *)s;}while(*s++); return 0; }
void *memset(void *d,int c,size_t n) { unsigned char *p=d; while(n--)*p++=c; return d; }
void *memcpy(void *d,const void *s,size_t n) { unsigned char *p=d; const unsigned char *q=s; while(n--)*p++=*q++; return d; }
int memcmp(const void *a,const void *b,size_t n) { const unsigned char *p=a,*q=b; while(n--){if(*p!=*q)return *p-*q; ++p;++q;} return 0; }
long atol(const char *s) { long v=0; int neg=0; while(*s==' '||*s=='\t')++s; if(*s=='-'||*s=='+')neg=(*s++=='-'); while(*s>='0'&&*s<='9')v=v*10+*s++-'0'; return neg?-v:v; }
int atoi(const char *s) { return atol(s); }
char *strerror(int e) { switch(e){case EINVAL:return "Invalid argument";case EFAULT:return "Bad address";case ENOSYS:return "Not implemented";case ENOENT:return "No such file";case EIO:return "I/O error";case EINTR:return "Interrupted";default:return "Guest error (see errno.h)";} }
static unsigned char heap[131072]; static unsigned used;
void *malloc(size_t n) { void *p; if(n>sizeof(heap)){errno=ENOMEM;return 0;} n=(n+3)&~3U; if(n>sizeof(heap)-used){errno=ENOMEM;return 0;} p=heap+used;used+=n;return p; }
void free(void *p) { (void)p; }
void *calloc(size_t n,size_t s) { void *p; if(s && n>0xffffffffU/s){errno=ENOMEM;return 0;} p=malloc(n*s);if(p)memset(p,0,n*s);return p; }

static FILE fds[3]={{0,0},{1,0},{2,0}};
FILE *stdin=&fds[0], *stdout=&fds[1], *stderr=&fds[2];
static void outchar(char *b,size_t cap,size_t *used,char c) { if(cap && *used<cap-1)b[*used]=c; ++*used; }
int vsnprintf(char *b,size_t cap,const char *fmt,va_list ap) {
    size_t n=0; const char *s; char tmp[32],pad; unsigned long v; int longarg,width,i,neg;
    while(*fmt) {
        if(*fmt!='%'){outchar(b,cap,&n,*fmt++);continue;}
        ++fmt; if(*fmt=='%'){outchar(b,cap,&n,*fmt++);continue;}
        pad=' '; if(*fmt=='0'){pad='0';++fmt;}
        width=0;while(*fmt>='0'&&*fmt<='9')width=width*10+*fmt++-'0';
        longarg=0; if(*fmt=='l'||*fmt=='z'){longarg=1;++fmt;}
        if(*fmt=='s'){s=va_arg(ap,const char *); if(!s)s="(null)";while(*s)outchar(b,cap,&n,*s++);}
        else if(*fmt=='c'){outchar(b,cap,&n,va_arg(ap,int));}
        else if(*fmt=='d'||*fmt=='i'||*fmt=='u'||*fmt=='x'||*fmt=='p') {
            int base=(*fmt=='x'||*fmt=='p')?16:10;
            neg=0;
            if(*fmt=='d'||*fmt=='i'){long x=longarg?va_arg(ap,long):va_arg(ap,int);neg=x<0;v=neg?0UL-(unsigned long)x:(unsigned long)x;}
            else v=longarg?va_arg(ap,unsigned long):va_arg(ap,unsigned int);
            i=0;do{tmp[i++]="0123456789abcdef"[v%base];v/=base;}while(v);
            if(neg && pad=='0')outchar(b,cap,&n,'-');
            while(width-- > i+neg)outchar(b,cap,&n,pad);
            if(neg && pad!='0')outchar(b,cap,&n,'-');
            while(i)outchar(b,cap,&n,tmp[--i]);
        } else {outchar(b,cap,&n,'?');}
        if(*fmt)++fmt;
    }
    if(cap)b[n<cap?n:cap-1]=0; return n;
}
int snprintf(char *b,size_t cap,const char *f,...) { va_list a;int n;va_start(a,f);n=vsnprintf(b,cap,f,a);va_end(a);return n; }
int sprintf(char *b,const char *f,...) { va_list a;int n;va_start(a,f);n=vsnprintf(b,0x7fffffff,f,a);va_end(a);return n; }
static int write_all(int fd,const char *b,unsigned n) { unsigned done=0;int r;while(done<n){r=write(fd,b+done,n-done);if(r<0&&errno==EINTR)continue;if(r<=0)return -1;done+=r;}return done; }
int fprintf(FILE *f,const char *fmt,...) { char b[2048];int n;va_list a;va_start(a,fmt);n=vsnprintf(b,sizeof(b),fmt,a);va_end(a);if(n>=sizeof(b)){errno=EINVAL;return -1;}return write_all(f->fd,b,n); }
int printf(const char *fmt,...) { char b[2048];int n;va_list a;va_start(a,fmt);n=vsnprintf(b,sizeof(b),fmt,a);va_end(a);if(n>=sizeof(b)){errno=EINVAL;return -1;}return write_all(1,b,n); }
int fputs(const char *s,FILE *f) { return write_all(f->fd,s,strlen(s)); }
int puts(const char *s) { if(write_all(1,s,strlen(s))<0)return -1;return write_all(1,"\n",1); }
int putchar(int c) { char b=c;return write(1,&b,1)<0?EOF:(unsigned char)b; }
int getchar(void) { unsigned char c;return read(0,&c,1)==1?c:EOF; }
int fflush(FILE *f) { (void)f;return 0; }
void perror(const char *s) { fprintf(stderr,"%s: %s (errno=%d)\n",s,strerror(errno),errno); }
FILE *fopen(const char *p,const char *mode) { FILE *f;int flags=O_RDONLY,fd;if(*mode=='w')flags=O_WRONLY|O_CREAT|O_TRUNC;else if(*mode=='a')flags=O_WRONLY|O_CREAT|O_APPEND;fd=open(p,flags,0644);if(fd<0)return 0;f=malloc(sizeof(*f));if(!f){close(fd);return 0;}f->fd=fd;f->owned=1;return f; }
int fclose(FILE *f) { return close(f->fd); }
size_t fwrite(const void *p,size_t s,size_t n,FILE *f) { int r;if(!s)return 0;r=write_all(f->fd,p,s*n);return r<0?0:r/s; }
size_t fread(void *p,size_t s,size_t n,FILE *f) { unsigned done=0;int r;if(!s)return 0;while(done<s*n){r=read(f->fd,(char *)p+done,s*n-done);if(r<0&&errno==EINTR)continue;if(r<=0)break;done+=r;}return done/s; }
char *fgets(char *p,int n,FILE *f) { int i=0;char c;while(i+1<n&&read(f->fd,&c,1)==1){p[i++]=c;if(c=='\n')break;}p[i]=0;return i?p:0; }
