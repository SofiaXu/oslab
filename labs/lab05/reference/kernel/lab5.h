#ifndef LAB5_H
#define LAB5_H
#include <linux/sched.h>

/* Every word is four bytes in the required i386 ABI. */
struct lab5_switch_frame {
    unsigned long gs, fs, es, ds;
    unsigned long edi, esi, ebx, ebp;
    unsigned long eflags, eip;
};
struct lab5_syscall_frame {
    unsigned long eax, ebx, ecx, edx, fs, es, ds;
    unsigned long eip, cs, eflags, esp, ss;
};
struct lab5_fork_frame {
    struct lab5_switch_frame sw;
    struct lab5_syscall_frame user;
};
void lab5_fork_return(void);
void lab5_init_stack(struct task_struct *p,
    long ebp, long edi, long esi, long gs,
    long ebx, long ecx, long edx, long fs, long es, long ds,
    long eip, long cs, long eflags, long esp, long ss);
#endif
