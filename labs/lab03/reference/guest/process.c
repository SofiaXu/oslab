/* Three children overlap. Parent collects real kernel records, never fabricates. */
#include <stdlib.h>
#include <sys/times.h>
#include <sys/wait.h>
#include "../../guest/trace_user.h"
static void workload(int kind)
{
    struct tms t;
    long start;
    volatile unsigned long work = 1;
    int i;
    if (kind == 2) {
        for (i = 0; i < 3; ++i) sleep(1);
    } else {
        start = times(&t);
        do {
            for (i = 0; i < 5000; ++i) work = work * 1664525UL + 1013904223UL;
        } while (times(&t) - start < 300);
    }
    _exit(0);
}
int main(int argc, char **argv)
{
    int fd, i, p, live = 0, status, bad = 0;
    int children[3];
    int quantum = argc > 1 ? atoi(argv[1]) : 15;
    fd = open("/var/process.log", O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) { perror("/var/process.log"); return 1; }
    if (trace_quantum(quantum) < 0 || drain_trace(fd) < 0) {
        perror("trace setup"); close(fd); return 1;
    }
    for (i = 0; i < 3; ++i) {
        p = fork();
        if (!p) { close(fd); workload(i); }
        if (p < 0) { perror("fork"); bad = 1; break; }
        children[live++] = p;
        printf("CHILD %d\n", p);
    }
    printf("SELECTED");
    for (i = 0; i < live; ++i) printf(" %d", children[i]);
    printf("\n");
    while (live) {
        if (drain_trace(fd) < 0) { bad = 1; break; }
        p = waitpid(-1, &status, WNOHANG);
        if (p > 0) { --live; if (status) bad = 1; }
        else if (!p) sleep(1);
        else if (errno != EINTR) { perror("waitpid"); bad = 1; break; }
    }
    if (drain_trace(fd) < 0) bad = 1;
    close(fd);
    sync();
    if (bad) { puts("LAB03 FAIL"); return 1; }
    printf("LAB03 PASS quantum=%d; export /var/process.log and analyze SELECTED PIDs\n", quantum);
    return 0;
}
