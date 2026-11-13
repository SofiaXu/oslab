/* 学生任务：作业准入策略不是 CPU 调度策略。接口见 docs/lab06.md。 */
#include <stdio.h>
#define MEMORY_K 100
#define MAX_JOBS 128
typedef enum { WAITING, RESIDENT, DONE } JobState;
typedef struct {
    char user[32], name[32];
    int duration, memory, tapes, start, admission_order;
    JobState state;
} Job;
typedef struct {
    Job jobs[MAX_JOBS]; int count;
    int memory_owner[MEMORY_K]; /* 0 空闲，正数为作业下标+1。 */
    int used_tapes, resident_count;
    long clock;
} System;
int first_fit(const System *sys, int size) {
    (void)sys; (void)size;
    /* TODO 1: 找第一个足够长的连续空闲区，返回起点；失败返回 -1。 */
    return -1;
}
int admit_jobs(System *sys, int use_sjf) {
    (void)sys; (void)use_sjf;
    /* TODO 2: 在可行作业中按 FCFS/SJF 选择；资源不足时继续查找。
       最多两道驻留。SJF 同时长按输入顺序。更新全部资源和状态。 */
    return -1;
}
int complete_job(System *sys, int index) {
    (void)sys; (void)index;
    /* TODO 3: 只允许完成驻留作业；释放连续内存与磁带，合并空闲区。 */
    return -1;
}
int main(int argc, char **argv) {
    (void)argc; (void)argv;
    /* TODO 4: 读取作业表，实现 auto/manual 两种入口。
       auto 使用单 CPU、非抢占、准入顺序执行；manual 使用 ADMIT/COMPLETE。
       输出作业表、空闲分区与事件时间，不要真实 sleep。 */
    fprintf(stderr, "INCOMPLETE lab06: implement allocation, admission, completion and CLI\n");
    return 3;
}
