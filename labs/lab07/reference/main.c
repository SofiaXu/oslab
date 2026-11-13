/* 固定物理块模拟。时间戳为引用位置，LFU 频率在重新调入时归 1。 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <errno.h>
#define MAXREF 100000
#define MAXFRAME 64
static int pages[MAXREF],n;
static void die(const char *s) { fprintf(stderr,"ERROR %s\n",s); exit(2); }
static unsigned long num(const char *s,unsigned long max) {
    char *e; unsigned long v; errno=0; v=strtoul(s,&e,10);
    if(errno||!*s||*s=='-'||*e||v>max) die("invalid nonnegative integer");
    return v;
}
static void load(const char *path) {
    FILE *f=!strcmp(path,"-")?stdin:fopen(path,"r"); char s[128];
    if(!f) die("cannot open sequence");
    while(fscanf(f,"%127s",s)==1) {
        if(n==MAXREF) die("too many references");
        pages[n++]=(int)num(s,1000000);
    }
    if(ferror(f)) die("sequence read failed");
    if(f!=stdin) fclose(f);
    if(!n) die("empty sequence");
}
static void save(const char *path) {
    FILE *f=fopen(path,"w"); if(!f) die("cannot create sequence");
    for(int i=0;i<n;i++) if(fprintf(f,"%d%c",pages[i],i+1==n?'\n':' ')<0) die("sequence write failed");
    if(fclose(f)) die("sequence close failed");
}
static void simulate(const char *alg,int cap,int step,FILE *keys) {
    int frame[MAXFRAME],born[MAXFRAME]={0},last[MAXFRAME]={0},freq[MAXFRAME]={0};
    int used=0,faults=0,replacements=0;
    for(int i=0;i<cap;i++) frame[i]=-1;
    for(int t=0;t<n;t++) {
        if(step) {
            char line[64]; fprintf(stderr,"Enter: next reference %d\n",t+1);
            if(!fgets(line,sizeof(line),keys)) die("step input ended before simulation completed");
        }
        int at=-1,victim=-1,hit=0;
        for(int i=0;i<used;i++) if(frame[i]==pages[t]) { at=i; hit=1; break; }
        if(!hit) {
            faults++;
            if(used<cap) at=used++;
            else {
                at=0; replacements++;
                for(int i=1;i<used;i++) {
                    int better=0;
                    if(!strcmp(alg,"fifo")) better=born[i]<born[at];
                    else if(!strcmp(alg,"lru")) better=last[i]<last[at];
                    else better=freq[i]<freq[at]||(freq[i]==freq[at]&&born[i]<born[at]);
                    if(better) at=i;
                }
                victim=frame[at];
            }
            frame[at]=pages[t]; born[at]=t; freq[at]=0;
        }
        last[at]=t; freq[at]++;
        printf("STEP %d page=%d %s victim=%d frames=",t+1,pages[t],hit?"HIT":"FAULT",victim);
        for(int i=0;i<cap;i++) printf("%s%d",i?",":"",frame[i]);
        printf(" faults=%d replacements=%d fault_rate=%.6f replacement_rate=%.6f\n",
            faults,replacements,(double)faults/(t+1),(double)replacements/(t+1));
    }
    printf("SUMMARY alg=%s frames=%d references=%d faults=%d replacements=%d fault_rate=%.6f replacement_rate=%.6f\n",
        alg,cap,n,faults,replacements,(double)faults/n,(double)replacements/n);
}
int main(int argc,char **argv) {
    if(argc==6&&!strcmp(argv[1],"generate")) {
        uint32_t seed=(uint32_t)num(argv[2],UINT32_MAX);
        n=(int)num(argv[3],MAXREF); int range=(int)num(argv[4],1000001);
        if(!n||!range) die("count and page range must be positive");
        for(int i=0;i<n;i++) { seed=1664525u*seed+1013904223u; pages[i]=(int)(seed%(uint32_t)range); }
        save(argv[5]); printf("GENERATED %d\n",n); return 0;
    }
    if(argc<5||strcmp(argv[1],"run") || (strcmp(argv[2],"fifo")&&strcmp(argv[2],"lru")&&strcmp(argv[2],"lfu")&&strcmp(argv[2],"all")))
        die("usage: lab07 run fifo|lru|lfu|all FRAMES FILE|- [--step] [--save FILE]; lab07 generate SEED COUNT PAGE_RANGE FILE");
    int cap=(int)num(argv[3],MAXFRAME),step=0; const char *out=NULL;
    if(!cap) die("frames must be 1..64");
    for(int i=5;i<argc;i++) {
        if(!strcmp(argv[i],"--step")&&!step) step=1;
        else if(!strcmp(argv[i],"--save")&&!out&&i+1<argc) out=argv[++i];
        else die("unknown/repeated option");
    }
    if(step&&!strcmp(argv[4],"-")) die("step requires a sequence file; stdin is used for Enter keys");
    load(argv[4]); if(out) save(out);
    if(!strcmp(argv[2],"all")) {
        simulate("fifo",cap,step,stdin); simulate("lru",cap,step,stdin); simulate("lfu",cap,step,stdin);
    } else simulate(argv[2],cap,step,stdin);
    return 0;
}
