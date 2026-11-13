/* i386 cdecl: void lab5_switch(struct task_struct *next, unsigned long ldt).
 * Caller-saved EAX/ECX/EDX may change. All callee-saved registers, segment
 * selectors and incoming EFLAGS (including IF) belong to the suspended task.
 * DS/ES are kernel selectors on entry. Linux 0.11 shares one CR3 across tasks.
 */
#include "lab5_offsets.inc"
    .text
    .code32
    .globl lab5_switch, lab5_fork_return
    .extern current, last_task_used_math, lab5_bootstrap_tss
lab5_switch:
    pushfl                         /* Save IF BEFORE disabling interrupts. */
    cli
    pushl %ebp
    pushl %ebx
    pushl %esi
    pushl %edi
    push %ds
    push %es
    push %fs
    push %gs                       /* Low address: gs/fs/es/ds/edi/esi/ebx/ebp. */
    movl LAB5_NEXT+4(%esp), %edx    /* Return address at LAB5_NEXT, then next. */
    movl current, %eax
    cmpl %eax, %edx
    je .Lrestore                   /* Same task: no TS or LDT side effects. */
    movl %esp, LAB5_KERNEL_ESP(%eax)
    movl %edx, current

    /* TR remains _TSS(0). Ring 3 -> ring 0 will use this task's stack top. */
    leal LAB5_PAGE_SIZE(%edx), %ecx
    movl lab5_bootstrap_tss, %eax
    movl %ecx, LAB5_TSS_ESP0(%eax)
    movl LAB5_NEXT+8(%esp), %eax
    lldt %ax                       /* MUST precede restoring FS/GS caches. */

    /* Software switching does not set CR0.TS automatically, hardware did. */
    movl %cr0, %eax
    orl $8, %eax
    movl %eax, %cr0
    cmpl last_task_used_math, %edx
    jne .Lload
    clts                           /* Live x87 owner already is the next task. */
.Lload:
    movl LAB5_KERNEL_ESP(%edx), %esp /* From here, no access to the old stack. */
.Lrestore:
    pop %gs                        /* Reload hidden segment descriptor caches. */
    pop %fs                        /* FS may also have been 0x10 in kernel I/O. */
    pop %es
    pop %ds
    popl %edi
    popl %esi
    popl %ebx
    popl %ebp
    popfl                          /* Restore incoming IF, never unconditional STI. */
    ret
lab5_fork_return:
    /* EDI/ESI/EBP and GS already restored; the normal syscall path does rest. */
    jmp ret_from_sys_call
    .section .note.GNU-stack,"",@progbits
