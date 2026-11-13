#ifndef OSLAB_STDDEF_H
#define OSLAB_STDDEF_H
#include <sys/types.h>
#define offsetof(type, member) __builtin_offsetof(type, member)
#endif
