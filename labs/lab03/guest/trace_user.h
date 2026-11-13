#ifndef LAB03_TRACE_USER_H
#define LAB03_TRACE_USER_H
#include <stdio.h>
#include <errno.h>
#include <unistd.h>
#include <fcntl.h>
struct trace_record { long pid, tick, state; };
static int trace_read(struct trace_record *out, unsigned int bytes)
{
    long r;
    __asm__ volatile("int $0x80" : "=a"(r) : "0"(72), "b"(out), "c"(bytes) : "memory", "cc");
    if (r < 0) { errno = -r; return -1; }
    return r;
}
static int trace_quantum(int ticks)
{
    long r;
    __asm__ volatile("int $0x80" : "=a"(r) : "0"(73), "b"(ticks) : "memory", "cc");
    if (r < 0) { errno = -r; return -1; }
    return r;
}
static int write_all(int fd, const char *s, int n)
{
    int k;
    while (n) {
        k = write(fd, s, n);
        if (k < 0 && errno == EINTR) continue;
        if (k <= 0) return -1;
        s += k; n -= k;
    }
    return 0;
}
static int drain_trace(int fd)
{
    struct trace_record records[32];
    char line[96];
    int bytes, n, i, rounds;
    for (rounds = 0; rounds < 8192; ++rounds) {
        bytes = trace_read(records, sizeof(records));
        if (bytes < 0) {
            write_all(fd, "# LOST_OR_READ_ERROR\n", 21);
            perror("trace_read (overflow requires reboot)");
            return -1;
        }
        if (!bytes) return 0;
        if (bytes % sizeof(records[0])) return -1;
        n = bytes / sizeof(records[0]);
        for (i = 0; i < n; ++i) {
            bytes = sprintf(line, "%ld\t%c\t%ld\n", records[i].pid,
                            (int)records[i].state, records[i].tick);
            if (write_all(fd, line, bytes) < 0) return -1;
        }
    }
    puts("collector cannot catch up; discard this measurement");
    return -1;
}
#endif
