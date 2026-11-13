#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>

/* 实现接口与参考版一致，参见 docs/lab02.md。
 * TODO 1: 解析 --consumers/--max/--file/--unsafe，校验范围。
 * TODO 2: 独占创建文件，ftruncate + mmap(MAP_SHARED)，容量固定为 10。
 * TODO 3: sem_open 创建 empty=10、full=0、mutex=1，使用唯一名字。
 * TODO 4: fork 一个生产者和 N 个消费者；不能用线程代替。
 * TODO 5: 实现 P/V 顺序、环形下标和互斥区内 PID:number 输出。
 * TODO 6: 分配消费次数，处理 EINTR 和子进程失败，waitpid 回收。
 * TODO 7: 每个进程 sem_close，父进程 sem_unlink/unlink。
 * TODO 8: 实现只去掉互斥保护的 --unsafe 对照模式。
 * 建议每次只实现一个步骤，并对照指导书检查失败路径。
 */
int main(int argc, char **argv)
{
    (void)argc;
    (void)argv;
    fputs("TODO: lab02 学生骨架尚未实现；请完成文件共享环形缓冲区和多进程信号量同步。\n", stderr);
    return EXIT_FAILURE;
}
