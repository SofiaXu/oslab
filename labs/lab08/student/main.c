/* 学生任务：纯内存模拟；禁止调用 system/exec 等执行文件内容。 */
#include <stdio.h>
#define MAX_USERS 16
#define FILES_PER_USER 32
#define CONTENT_BYTES 1024
#define NAME_BYTES 32
enum { PERM_READ=1, PERM_WRITE=2, PERM_EXEC=4 };
typedef struct {
    char name[NAME_BYTES], content[CONTENT_BYTES+1];
    int used, permissions, opened;
} FileEntry;
typedef struct {
    char name[NAME_BYTES];
    FileEntry files[FILES_PER_USER];
    int open_count;
} UserDirectory;
typedef struct {
    UserDirectory users[MAX_USERS];
    int user_count, current_user, open_limit;
} FileSystem;
FileEntry *lookup(FileSystem *fs, const char *name) {
    (void)fs; (void)name;
    /* TODO 1: MFD 找当前用户，再在其 UFD 查找名字。不能查其他用户。 */
    return NULL;
}
int dispatch(FileSystem *fs, int argc, char **argv) {
    (void)fs; (void)argc; (void)argv;
    /* TODO 2: USER/LOGIN/CREATE/DELETE/OPEN/CLOSE/READ/WRITE/EXEC/LIST。
       所有操作先验证再修改；检查打开上限、权限、长度、重复名字等。
       EXEC 只输出模拟结果，不访问或执行宿主文件。 */
    return -1;
}
int main(int argc, char **argv) {
    (void)argc; (void)argv;
    /* TODO 3: 逐行读取并校验参数个数；初始化 current_user=-1。
       K 默认 2；错误命令不能使后续命令错位。
       切换用户保留各自打开表；退出不持久化。 */
    fprintf(stderr, "INCOMPLETE lab08: implement directories, open table, permissions and CLI\n");
    return 3;
}
