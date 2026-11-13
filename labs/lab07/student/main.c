/* 学生任务：固定物理块内置换，接口见 docs/lab07.md。 */
#include <stdio.h>
#define MAX_FRAMES 64
#define MAX_REFERENCES 100000
typedef enum { FIFO, LRU, LFU } Algorithm;
typedef struct {
    int page, loaded_at, last_used, frequency, occupied;
} Frame;
typedef struct {
    Frame frames[MAX_FRAMES];
    int frame_count, references, faults, replacements;
} Simulation;
int select_victim(const Simulation *sim, Algorithm algorithm) {
    (void)sim; (void)algorithm;
    /* TODO 1: 优先空块。FIFO 比较 loaded_at；LRU 比较 last_used；
       LFU 比较本次驻留 frequency，同频比较 loaded_at。 */
    return -1;
}
int access_page(Simulation *sim, int page, Algorithm algorithm) {
    (void)sim; (void)page; (void)algorithm;
    /* TODO 2: 查找命中；更新元数据；未命中计缺页；满内存才计置换。
       页面重新调入时频率必须重置。 */
    return -1;
}
int main(int argc, char **argv) {
    (void)argc; (void)argv;
    /* TODO 3: 实现 run/generate、文件和键盘输入、--step、--save。
       生成器按文档使用 uint32_t LCG，保证跨机器重放一致。
       三种算法比较时，每次重置 Simulation，保留相同引用序列。 */
    fprintf(stderr, "INCOMPLETE lab07: implement replacement policies, sequence I/O and CLI\n");
    return 3;
}
