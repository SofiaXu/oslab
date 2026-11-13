/* 银行家算法：安全检查只操作 work/finish，试探分配使用完整状态副本。 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#define N 32
#define LIMIT 1000000
static void die(const char *s) { fprintf(stderr,"ERROR %s\n",s); exit(2); }
static int token(FILE *f,char *s) { return fscanf(f,"%127s",s)==1; }
static int number(FILE *f) {
    char s[128],*end; long v;
    if(!token(f,s)) die("missing integer");
    errno=0; v=strtol(s,&end,10);
    if(errno||*end||v<0||v>LIMIT) die("integer must be 0..1000000");
    return (int)v;
}
typedef struct { int n,m,av[N],max[N][N],alloc[N][N]; } State;
static int safe(const State *s,int seq[N]) {
    long work[N]; int done[N]={0},k=0;
    for(int j=0;j<s->m;j++) work[j]=s->av[j];
    while(k<s->n) {
        int progress=0;
        for(int i=0;i<s->n;i++) if(!done[i]) {
            int j;
            for(j=0;j<s->m;j++) if(s->max[i][j]-s->alloc[i][j]>work[j]) break;
            if(j==s->m) {
                done[i]=1; seq[k++]=i; progress=1;
                for(j=0;j<s->m;j++) work[j]+=s->alloc[i][j];
            }
        }
        if(!progress) return 0;
    }
    return 1;
}
static void safety(const State *s) {
    int seq[N];
    if(!safe(s,seq)) { puts("UNSAFE"); return; }
    printf("SAFE"); for(int i=0;i<s->n;i++) printf(" P%d",seq[i]); puts("");
}
static void show(const State *s) {
    printf("AVAILABLE"); for(int j=0;j<s->m;j++) printf(" %d",s->av[j]);
    puts("\nPID MAX | ALLOC | NEED");
    for(int i=0;i<s->n;i++) {
        printf("P%d",i);
        for(int j=0;j<s->m;j++) printf(" %d",s->max[i][j]);
        printf(" |"); for(int j=0;j<s->m;j++) printf(" %d",s->alloc[i][j]);
        printf(" |"); for(int j=0;j<s->m;j++) printf(" %d",s->max[i][j]-s->alloc[i][j]);
        puts("");
    }
}
int main(int argc,char **argv) {
    State s={0}; char cmd[128]; FILE *f; int errors=0;
    if(argc!=2) die("usage: lab04 STATE_FILE (commands from stdin: SHOW SAFE REQUEST pid r... QUIT)");
    f=fopen(argv[1],"r"); if(!f) die("cannot open state");
    s.n=number(f); s.m=number(f);
    if(s.n<1||s.n>N||s.m<1||s.m>N) die("dimensions must be 1..32");
    for(int j=0;j<s.m;j++) s.av[j]=number(f);
    for(int i=0;i<s.n;i++) for(int j=0;j<s.m;j++) s.max[i][j]=number(f);
    for(int i=0;i<s.n;i++) for(int j=0;j<s.m;j++) {
        s.alloc[i][j]=number(f);
        if(s.alloc[i][j]>s.max[i][j]) die("allocation exceeds maximum");
    }
    if(token(f,cmd)) die("trailing state data");
    fclose(f); show(&s); safety(&s);
    while(token(stdin,cmd)) {
        if(!strcmp(cmd,"QUIT")) break;
        if(!strcmp(cmd,"SHOW")) show(&s);
        else if(!strcmp(cmd,"SAFE")) safety(&s);
        else if(!strcmp(cmd,"REQUEST")) {
            int pid=number(stdin),r[N],seq[N]; const char *reason=NULL;
            for(int j=0;j<s.m;j++) r[j]=number(stdin);
            if(pid>=s.n) reason="pid";
            else {
                for(int j=0;j<s.m;j++) if(r[j]>s.max[pid][j]-s.alloc[pid][j]) reason="exceeds_need";
                if(!reason) for(int j=0;j<s.m;j++) if(r[j]>s.av[j]) reason="unavailable";
            }
            if(!reason) {
                State trial=s;
                for(int j=0;j<s.m;j++) { trial.av[j]-=r[j]; trial.alloc[pid][j]+=r[j]; }
                if(safe(&trial,seq)) s=trial; else reason="unsafe_rollback";
            }
            if(reason) { printf("DENIED %s\n",reason); errors=1; }
            else { puts("GRANTED"); safety(&s); }
            show(&s);
        } else die("unknown command");
    }
    if(ferror(stdin)) die("input read failed");
    return errors?1:0;
}
