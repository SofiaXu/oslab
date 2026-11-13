/* A fork child has never called schedule(): manufacture its first return. */
#include "lab5.h"

typedef char lab5_i386_only[(sizeof(unsigned long) == 4) ? 1 : -1];
typedef char lab5_stack_room[(sizeof(struct task_struct) +
    sizeof(struct lab5_fork_frame) + 512 < PAGE_SIZE) ? 1 : -1];

void lab5_init_stack(struct task_struct *p,
    long ebp, long edi, long esi, long gs,
    long ebx, long ecx, long edx, long fs, long es, long ds,
    long eip, long cs, long eflags, long esp, long ss)
{
    struct lab5_fork_frame *f;
    f = (struct lab5_fork_frame *)((unsigned long)p + PAGE_SIZE - sizeof(*f));
    f->sw.gs = gs & 0xffff;
    f->sw.fs = 0x17; /* Kernel convention: access current user's data via FS. */
    f->sw.es = f->sw.ds = 0x10;
    f->sw.edi = edi;
    f->sw.esi = esi;
    f->sw.ebx = ebx;
    f->sw.ebp = ebp;
    f->sw.eflags = 2; /* IF=0 until iret installs the user's original flags. */
    f->sw.eip = (unsigned long)lab5_fork_return;
    f->user.eax = 0; /* fork returns zero in the child. */
    f->user.ebx = ebx;
    f->user.ecx = ecx;
    f->user.edx = edx;
    f->user.fs = fs & 0xffff;
    f->user.es = es & 0xffff;
    f->user.ds = ds & 0xffff;
    f->user.eip = eip;
    f->user.cs = cs & 0xffff;
    f->user.eflags = eflags;
    f->user.esp = esp;
    f->user.ss = ss & 0xffff;
    p->kernel_esp = (unsigned long)f;
}
