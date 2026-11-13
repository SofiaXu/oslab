#ifndef LAB01_API_H
#define LAB01_API_H
#include <errno.h>
static int iam(const char *name)
{
    long r;
    __asm__ volatile("int $0x80" : "=a"(r) : "0"(72), "b"(name) : "memory", "cc");
    if (r < 0) { errno = -r; return -1; }
    return r;
}
static int whoami(char *buffer, unsigned int size)
{
    long r;
    __asm__ volatile("int $0x80" : "=a"(r) : "0"(73), "b"(buffer), "c"(size) : "memory", "cc");
    if (r < 0) { errno = -r; return -1; }
    return r;
}
#endif
