/* 学生任务：只修改本目录，不包含 reference 源码。接口见 docs/lab04.md。 */
#include <stdio.h>
#define MAX_PROCESSES 32
#define MAX_RESOURCES 32
typedef struct {
    int n, m;
    int available[MAX_RESOURCES];
    int maximum[MAX_PROCESSES][MAX_RESOURCES];
    int allocation[MAX_PROCESSES][MAX_RESOURCES];
} State;
/* 返回 1=安全，0=不安全，-1=尚未实现；sequence 存放安全序列。 */
int safety_check(const State *state, int sequence[]) {
    (void)state; (void)sequence;
    /* TODO 1: 从 available 复制 work；循环寻找 need<=work 的未完成进程。
       不能直接修改 state。注意“本轮没有进展”的终止条件。 */
    return -1;
}
int request_resources(State *state, int pid, const int request[]) {
    (void)state; (void)pid; (void)request;
    /* TODO 2: 检查 pid、非负、need、available；试探分配后检查安全性。
       不安全时恢复所有数据，不能只恢复 available。 */
    return -1;
}
int main(int argc, char **argv) {
    (void)argc; (void)argv;
    /* TODO 3: 读取状态文件，检查维度及 allocation<=maximum。
       实现 SHOW/SAFE/REQUEST/QUIT，输出矩阵和具体拒绝原因。
       先用 fixtures/classic.txt 对照手算，再编写自己的数据。 */
    fprintf(stderr, "INCOMPLETE lab04: implement input, safety_check and request_resources\n");
    return 3;
}
