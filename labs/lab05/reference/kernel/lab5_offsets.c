/* Compile, never execute: offsets are computed by the target i386 compiler. */
#include "lab5.h"
#define OFFSET(name, type, member) \
    __asm__ volatile("\n.equ " #name ", %c0" : : \
                     "i" (__builtin_offsetof(type, member)))
void lab5_emit_offsets(void)
{
    OFFSET(LAB5_KERNEL_ESP, struct task_struct, kernel_esp);
    OFFSET(LAB5_TSS_ESP0, struct tss_struct, esp0);
    __asm__ volatile("\n.equ LAB5_PAGE_SIZE, %c0" : : "i" (PAGE_SIZE));
    OFFSET(LAB5_NEXT, struct lab5_switch_frame, eip);
}
