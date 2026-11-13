#ifndef OSLAB_STDLIB_H
#define OSLAB_STDLIB_H
#include <stddef.h>
#define EXIT_SUCCESS 0
#define EXIT_FAILURE 1
int atoi(const char *);
long atol(const char *);
void *malloc(size_t);
void *calloc(size_t, size_t);
void free(void *);
void exit(int) __attribute__((noreturn));
void abort(void) __attribute__((noreturn));
#endif
