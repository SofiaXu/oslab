/* TODO_LAB5_SOFTWARE_SWITCH: ask AI to generate a SOFTWARE switch with the
 * interface in lab5.h/docs/lab05.md, then inspect, integrate and debug it.
 * This is an explicitly INCOMPLETE but bootable HARDWARE-switch fallback.
 * Do not submit it, or remove the marker without replacing the algorithm.
 */
    .text
    .code32
    .globl lab5_switch, lab5_fork_return
lab5_switch:
    pushfl
    cli
    pushl %ebp
    pushl %ebx
    pushl %esi
    pushl %edi
    movl 24(%esp), %ecx
    cmpl current, %ecx
    je 1f
    movl 28(%esp), %edx         /* LDT selector - 8 = this task's TSS selector. */
    subl $8, %edx
    subl $8, %esp
    movl $0, (%esp)
    movl %edx, 4(%esp)
    xchgl %ecx, current
    ljmp *(%esp)               /* Old hardware task switching: unfinished lab! */
    addl $8, %esp
    movl current, %eax
    cmpl last_task_used_math, %eax
    jne 1f
    clts
1:  popl %edi
    popl %esi
    popl %ebx
    popl %ebp
    popfl
    ret
lab5_fork_return:
    jmp ret_from_sys_call
    .section .note.GNU-stack,"",@progbits
