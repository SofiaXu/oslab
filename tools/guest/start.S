/* Linux 0.11 exec stack: argc, argv pointer, envp pointer (not modern ELF ABI).
 * No host libc, dynamic linker, PIE, or CRT is linked into guest executables. */
.section .text.start,"ax"
.globl _start
_start:
    xorl %ebp,%ebp
    movl %esp,%eax
    pushl 8(%eax)
    pushl 4(%eax)
    pushl (%eax)
    call main
    pushl %eax
    call _exit
1:  jmp 1b
.section .note.GNU-stack,"",@progbits
