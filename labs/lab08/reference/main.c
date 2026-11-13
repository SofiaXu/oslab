/* 所有目录、内容和打开状态均在内存。EXEC 仅输出文字，从不调用宿主命令。 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#define USERS 16
#define FILES 32
#define NAME 31
#define CONTENT 1024
#define R 1
#define W 2
#define X 4
typedef struct { int used,perm,opened; char name[NAME+1],data[CONTENT+1]; } File;
typedef struct { char name[NAME+1]; File files[FILES]; int opens; } User;
static User mfd[USERS]; static int count,current=-1,k=2,errors;
static void die(const char *s) { fprintf(stderr,"ERROR %s\n",s); exit(2); }
static void deny(const char *s) { printf("DENIED %s\n",s); errors=1; }
static int valid_name(const char *s) {
    size_t len=strlen(s); if(!len||len>NAME) return 0;
    for(size_t i=0;i<len;i++) if(!((s[i]>='a'&&s[i]<='z')||(s[i]>='A'&&s[i]<='Z')||
        (s[i]>='0'&&s[i]<='9')||s[i]=='_'||s[i]=='-')) return 0;
    return 1;
}
static int perms(const char *s) {
    int p=0; if(!strcmp(s,"-")) return 0;
    for(;*s;s++) {
        int bit=*s=='r'?R:*s=='w'?W:*s=='x'?X:0;
        if(!bit||(p&bit)) return -1;
        p|=bit;
    }
    return p;
}
static File *find(User *u,const char *name) {
    for(int i=0;i<FILES;i++) if(u->files[i].used&&!strcmp(u->files[i].name,name)) return &u->files[i];
    return NULL;
}
static void list(void) {
    for(int i=0;i<count;i++) {
        printf("USER %s opens=%d limit=%d\n",mfd[i].name,mfd[i].opens,k);
        for(int j=0;j<FILES;j++) {
            File *f=&mfd[i].files[j]; if(!f->used) continue;
            printf("FILE %s %s perm=%c%c%c open=%d length=%zu\n",mfd[i].name,f->name,
                f->perm&R?'r':'-',f->perm&W?'w':'-',f->perm&X?'x':'-',f->opened,strlen(f->data));
        }
    }
}
static void command(int n,char **v) {
    if(!strcmp(v[0],"USER")&&n==2) {
        if(!valid_name(v[1])) { deny("invalid_name"); return; }
        for(int i=0;i<count;i++) if(!strcmp(mfd[i].name,v[1])) { deny("user_exists"); return; }
        if(count==USERS) { deny("user_capacity"); return; }
        strcpy(mfd[count++].name,v[1]); puts("OK USER"); return;
    }
    if(!strcmp(v[0],"LOGIN")&&n==2) {
        for(int i=0;i<count;i++) if(!strcmp(mfd[i].name,v[1])) {
            current=i; printf("OK LOGIN %s\n",v[1]); return;
        }
        deny("unknown_user"); return;
    }
    if(!strcmp(v[0],"LIST")&&n==1) { list(); return; }
    if(current<0) { deny("login_required"); return; }
    User *u=&mfd[current];
    if(!strcmp(v[0],"CREATE")&&n==3) {
        int p=perms(v[2]);
        if(!valid_name(v[1])||p<0) { deny("invalid_name_or_permissions"); return; }
        if(find(u,v[1])) { deny("file_exists"); return; }
        for(int i=0;i<FILES;i++) if(!u->files[i].used) {
            File *f=&u->files[i]; memset(f,0,sizeof(*f)); f->used=1; f->perm=p;
            strcpy(f->name,v[1]); puts("OK CREATE"); return;
        }
        deny("file_capacity"); return;
    }
    int write=!strcmp(v[0],"WRITE");
    if((write&&n!=3)||(!write&&n!=2)||
        (strcmp(v[0],"OPEN")&&strcmp(v[0],"CLOSE")&&strcmp(v[0],"DELETE")&&
         strcmp(v[0],"READ")&&strcmp(v[0],"WRITE")&&strcmp(v[0],"EXEC"))) { deny("command"); return; }
    File *f=find(u,v[1]); if(!f) { deny("no_such_file"); return; }
    if(!strcmp(v[0],"OPEN")) {
        if(f->opened) deny("already_open");
        else if(u->opens==k) deny("open_limit");
        else { f->opened=1; u->opens++; puts("OK OPEN"); }
    } else if(!strcmp(v[0],"CLOSE")) {
        if(!f->opened) deny("not_open");
        else { f->opened=0; u->opens--; puts("OK CLOSE"); }
    } else if(!strcmp(v[0],"DELETE")) {
        if(f->opened) deny("file_open"); else { memset(f,0,sizeof(*f)); puts("OK DELETE"); }
    } else {
        int required=write?W:!strcmp(v[0],"READ")?R:X;
        if(!f->opened) deny("not_open");
        else if(!(f->perm&required)) deny("permission");
        else if(write) {
            if(strlen(v[2])>CONTENT) deny("content_capacity");
            else { strcpy(f->data,v[2]); puts("OK WRITE"); }
        } else if(required==R) printf("DATA %s\n",f->data);
        else printf("EXEC_SIMULATED %s/%s\n",u->name,f->name);
    }
}
int main(int argc,char **argv) {
    char line[2048],*v[8];
    if(argc>2) die("usage: lab08 [K=1..32]; commands from stdin");
    if(argc==2) {
        char *e; long val; errno=0; val=strtol(argv[1],&e,10);
        if(errno||!*argv[1]||*e||val<1||val>FILES) die("K must be 1..32");
        k=(int)val;
    }
    while(fgets(line,sizeof(line),stdin)) {
        if(!strchr(line,'\n')&&!feof(stdin)) die("line too long");
        int n=0; char *s=strtok(line," \t\r\n");
        while(s&&n<8) { v[n++]=s; s=strtok(NULL," \t\r\n"); }
        if(s) { deny("too_many_fields"); continue; }
        if(!n) continue;
        if(n==1&&!strcmp(v[0],"QUIT")) break;
        command(n,v);
    }
    if(ferror(stdin)) die("input read failed");
    return errors?1:0;
}
