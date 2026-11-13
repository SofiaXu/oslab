#ifndef LAB02_KERNEL_API_H
#define LAB02_KERNEL_API_H
#include <errno.h>
static int sem_call(int nr, long a, long b)
{
    long r;
    __asm__ volatile("int $0x80" : "=a"(r) : "0"(nr), "b"(a), "c"(b) : "memory", "cc");
    if (r < 0) { errno = -r; return -1; }
    return r;
}
static int sem_open(const char *name, unsigned int value)
{ return sem_call(72, (long)name, value); }
static int sem_wait(int id) { return sem_call(73, id, 0); }
static int sem_post(int id) { return sem_call(74, id, 0); }
static int sem_unlink(const char *name) { return sem_call(75, (long)name, 0); }
#endif
