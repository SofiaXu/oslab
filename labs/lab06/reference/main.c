/* 单 CPU 非抢占，按准入先后执行；FCFS/SJF 仅决定后备作业准入。 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <limits.h>
#define MAXJ 128
#define MEM 100
static void die(const char *s) { fprintf(stderr,"ERROR %s\n",s); exit(2); }
static int num(const char *s,int max) {
    char *e; long v; errno=0; v=strtol(s,&e,10);
    if(errno||!*s||*e||v<0||v>max) die("invalid integer");
    return (int)v;
}
typedef struct { char user[32],name[32]; int duration,mem,tapes,state,start,order; } Job;
static Job jobs[MAXJ]; static int n,ram[MEM],used_tapes,resident,serial,sjf; static long now;
/* 每个 K 一个格子。连续 0 段就是空闲分区，释放置 0 自然合并相邻分区。 */
static int first_fit(int size) {
    int run=0;
    for(int a=0;a<MEM;a++) { run=ram[a]?0:run+1; if(run==size) return a-size+1; }
    return -1;
}
static void show(void) {
    printf("STATE time=%ld resident=%d tapes_free=%d\n",now,resident,5-used_tapes);
    for(int i=0;i<n;i++) printf("JOB %s %s %s duration=%d mem=%d tapes=%d start=%d\n",
        jobs[i].user,jobs[i].name,(const char*[]){"WAIT","RESIDENT","DONE"}[jobs[i].state],
        jobs[i].duration,jobs[i].mem,jobs[i].tapes,jobs[i].start);
    for(int a=0;a<MEM;) {
        int b=a; if(ram[a]) { a++; continue; }
        while(a<MEM&&!ram[a]) a++;
        printf("HOLE start=%d size=%d\n",b,a-b);
    }
}
static void admit(void) {
    while(resident<2) {
        int pick=-1,pos=-1;
        for(int i=0;i<n;i++) if(!jobs[i].state&&jobs[i].tapes<=5-used_tapes) {
            int p=first_fit(jobs[i].mem);
            if(p>=0&&(pick<0||(sjf&&jobs[i].duration<jobs[pick].duration))) { pick=i; pos=p; }
        }
        if(pick<0) break;
        Job *j=&jobs[pick]; j->state=1; j->start=pos; j->order=serial++;
        for(int a=pos;a<pos+j->mem;a++) ram[a]=pick+1;
        used_tapes+=j->tapes; resident++;
        printf("ADMIT %s %s time=%ld start=%d\n",j->user,j->name,now,pos);
        show(); /* 每次准入后立即展示作业表与空闲分区。 */
    }
}
static int finish(int i) {
    if(i<0||jobs[i].state!=1) { puts("DENIED not_resident"); return 0; }
    Job *j=&jobs[i];
    for(int a=j->start;a<j->start+j->mem;a++) ram[a]=0;
    used_tapes-=j->tapes; resident--; j->state=2;
    printf("COMPLETE %s %s time=%ld\n",j->user,j->name,now); return 1;
}
/* 严格按行解析：输入表为 user job duration(minutes) memory(K) tapes。 */
static int split(char *s,char *v[],int cap) {
    int k=0; char *t=strtok(s," \t\r\n");
    while(t) { if(k==cap) die("too many fields"); v[k++]=t; t=strtok(NULL," \t\r\n"); }
    return k;
}
int main(int argc,char **argv) {
    FILE *f; char line[512],*v[8]; int errors=0;
    if(argc!=4|| (strcmp(argv[1],"fcfs")&&strcmp(argv[1],"sjf")) ||
        (strcmp(argv[2],"auto")&&strcmp(argv[2],"manual")))
        die("usage: lab06 fcfs|sjf auto|manual JOB_FILE");
    sjf=!strcmp(argv[1],"sjf"); f=fopen(argv[3],"r"); if(!f) die("cannot open jobs");
    while(fgets(line,sizeof(line),f)) {
        if(!strchr(line,'\n')&&!feof(f)) die("line too long");
        int k=split(line,v,8); if(!k) continue;
        if(k!=5||n==MAXJ||strlen(v[0])>31||strlen(v[1])>31) die("invalid job row");
        for(int i=0;i<n;i++) if(!strcmp(jobs[i].user,v[0])&&!strcmp(jobs[i].name,v[1])) die("duplicate job");
        Job *j=&jobs[n++]; strcpy(j->user,v[0]); strcpy(j->name,v[1]);
        j->duration=num(v[2],1000000); j->mem=num(v[3],MEM); j->tapes=num(v[4],5); j->start=-1;
        if(!j->duration||!j->mem) die("duration/memory must be positive");
    }
    if(ferror(f)||!n) die("empty or unreadable job table");
    fclose(f); show();
    if(!strcmp(argv[2],"auto")) {
        int completed=0;
        while(completed<n) {
            admit(); show(); int p=-1;
            for(int i=0;i<n;i++) if(jobs[i].state==1&&(p<0||jobs[i].order<jobs[p].order)) p=i;
            if(p<0) die("no progress");
            now+=jobs[p].duration; finish(p); completed++;
        }
        show(); puts("ALL_DONE");
    } else {
        while(fgets(line,sizeof(line),stdin)) {
            if(!strchr(line,'\n')&&!feof(stdin)) die("line too long");
            int k=split(line,v,8); if(!k) continue;
            if(k==1&&!strcmp(v[0],"QUIT")) break;
            if(k==1&&!strcmp(v[0],"ADMIT")) admit();
            else if(k==1&&!strcmp(v[0],"SHOW")) { show(); continue; }
            else if(k==3&&!strcmp(v[0],"COMPLETE")) {
                int p=-1;
                for(int i=0;i<n;i++) if(!strcmp(jobs[i].user,v[1])&&!strcmp(jobs[i].name,v[2])) p=i;
                if(!finish(p)) errors=1;
            } else { puts("DENIED command"); errors=1; }
            show();
        }
        if(ferror(stdin)) die("input read failed");
    }
    return errors?1:0;
}
