/* Linux 0.11 guest ONLY. C89 plus GNU i386 asm; no floating-point libc needed.
 * Build with the suite's freestanding guest runtime, NOT Ubuntu's glibc.
 * Output: LAB05_PASS or LAB05_FAIL to stdout AND /var/lab05.result.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <sys/wait.h>

extern int lab5_checked_fork(void);
extern int lab5_register_probe(int loops, int seed);

/* Check the very FIRST child return, before a C prologue overwrites registers.
 * A live x87 value spans fork in BOTH parent and child; this catches the
 * FNSAVE-without-FRSTOR parent-state bug as well as incorrect child frames.
 */
__asm__(
".text\n"
".globl lab5_checked_fork\n"
"lab5_checked_fork:\n"
" pushl %ebp\n pushl %ebx\n pushl %esi\n pushl %edi\n subl $8,%esp\n"
" movl $169,4(%esp)\n fildl 4(%esp)\n"
" movl $0x11111111,%ebx\n movl $0x22222222,%ecx\n"
" movl $0x33333333,%edx\n movl $0x44444444,%edi\n"
" movl $0x55555555,%esi\n movl $0x66666666,%ebp\n"
" movl $2,%eax\n int $0x80\n movl %eax,(%esp)\n"
" cmpl $0x11111111,%ebx\n jne 1f\n"
" cmpl $0x22222222,%ecx\n jne 1f\n"
" cmpl $0x33333333,%edx\n jne 1f\n"
" cmpl $0x44444444,%edi\n jne 1f\n"
" cmpl $0x55555555,%esi\n jne 1f\n"
" cmpl $0x66666666,%ebp\n jne 1f\n jmp 2f\n"
"1: movl $-99,(%esp)\n"
"2: fistpl 4(%esp)\n cmpl $169,4(%esp)\n je 3f\n"
" movl $-98,(%esp)\n"
"3: movl (%esp),%eax\n addl $8,%esp\n"
" popl %edi\n popl %esi\n popl %ebx\n popl %ebp\n ret\n"
);

/* Keep six process-specific integer sentinels, ST(0), and x87 rounding mode
 * live across CPU work, syscalls, timer interrupts, and context switches.
 * The 48 local bytes and four saved registers place args at esp+68/+72.
 * Return 1=integer regs, 2=x87 value, 3=x87 CW, 4=segments, 5=EFLAGS.
 */
__asm__(
".text\n.globl lab5_register_probe\n"
"lab5_register_probe:\n"
" pushl %ebp\n pushl %ebx\n pushl %esi\n pushl %edi\n subl $48,%esp\n"
" movl 68(%esp),%eax\n movl %eax,12(%esp)\n"
" fnstcw 44(%esp)\n movzwl 44(%esp),%eax\n andl $0xf3ff,%eax\n"
" movl 72(%esp),%edx\n andl $3,%edx\n shll $10,%edx\n orl %edx,%eax\n"
" movw %ax,4(%esp)\n fldcw 4(%esp)\n fildl 72(%esp)\n"
" movl 72(%esp),%eax\n addl $0x11111111,%eax\n movl %eax,16(%esp)\n"
" addl $0x11111111,%eax\n movl %eax,20(%esp)\n"
" addl $0x11111111,%eax\n movl %eax,24(%esp)\n"
" addl $0x11111111,%eax\n movl %eax,28(%esp)\n"
" addl $0x11111111,%eax\n movl %eax,32(%esp)\n"
" addl $0x11111111,%eax\n movl %eax,36(%esp)\n"
" movl 16(%esp),%ebx\n movl 20(%esp),%ecx\n movl 24(%esp),%edx\n"
" movl 28(%esp),%edi\n movl 32(%esp),%esi\n movl 36(%esp),%ebp\n"
"4: movl $128,%eax\n5: decl %eax\n jne 5b\n"
" movl $20,%eax\n int $0x80\n"
" cmpl 16(%esp),%ebx\n jne 6f\n cmpl 20(%esp),%ecx\n jne 6f\n"
" cmpl 24(%esp),%edx\n jne 6f\n cmpl 28(%esp),%edi\n jne 6f\n"
" cmpl 32(%esp),%esi\n jne 6f\n cmpl 36(%esp),%ebp\n jne 6f\n"
" fistl (%esp)\n movl (%esp),%eax\n cmpl 72(%esp),%eax\n jne 7f\n"
" fnstcw 8(%esp)\n movw 8(%esp),%ax\n cmpw 4(%esp),%ax\n jne 8f\n"
" movw %ds,%ax\n cmpw $0x17,%ax\n jne 9f\n"
" movw %es,%ax\n cmpw $0x17,%ax\n jne 9f\n"
" movw %fs,%ax\n cmpw $0x17,%ax\n jne 9f\n"
" movw %gs,%ax\n cmpw $0x17,%ax\n jne 9f\n"
" pushfl\n popl %eax\n andl $0x600,%eax\n cmpl $0x200,%eax\n jne 10f\n"
" decl 12(%esp)\n jnz 4b\n xorl %eax,%eax\n jmp 11f\n"
"6: movl $1,%eax\n jmp 11f\n"
"7: movl $2,%eax\n jmp 11f\n"
"8: movl $3,%eax\n jmp 11f\n"
"9: movl $4,%eax\n jmp 11f\n"
"10: movl $5,%eax\n"
"11: fstp %st(0)\n fldcw 44(%esp)\n addl $48,%esp\n"
" popl %edi\n popl %esi\n popl %ebx\n popl %ebp\n ret\n"
);

static int result(int ok)
{
    const char *text;
    int fd, n;
    text = ok < 0 ? "LAB05_RUNNING\n" :
        (ok ? "LAB05_PASS\n" : "LAB05_FAIL\n");
    n = strlen(text);
    fd = open("/var/lab05.result", O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd >= 0) {
        if (write(fd, text, n) != n)
            printf("lab05: result file write failed\n");
        close(fd);
    } else {
        printf("lab05: result file unavailable, use stdout marker\n");
    }
    write(1, text, n);
    return ok != 0 ? 0 : 1;
}

int main(int argc, char **argv)
{
    int rounds, loops, r, i, pid, count, status, rc, bad;
    rounds = argc > 1 ? atoi(argv[1]) : 4;
    loops = argc > 2 ? atoi(argv[2]) : 60000;
    if (rounds < 1 || rounds > 64 || loops < 1 || loops > 5000000) {
        printf("usage: lab05_test [rounds:1..64] [loops:1..5000000]\n");
        return result(0);
    }
    /* Erase a stale PASS immediately; a later crash must not look successful. */
    result(-1);
    bad = 0;
    for (r = 0; r < rounds; ++r) {
        count = 0;
        for (i = 0; i < 4; ++i) {
            pid = lab5_checked_fork();
            if (pid < 0) {
                printf("lab05: fork/probe failed (%d)\n", pid);
                bad = 1;
                break;
            }
            if (pid == 0) {
                rc = lab5_register_probe(loops, (getpid() % 10000) + 1);
                if (rc)
                    printf("lab05: child %d probe=%d\n", getpid(), rc);
                _exit(rc);
            }
            ++count;
        }
        rc = lab5_register_probe(loops, (getpid() % 10000) + 1);
        if (rc) {
            printf("lab05: parent probe=%d\n", rc);
            bad = 1;
        }
        while (count > 0) {
            pid = wait(&status);
            if (pid < 0) {
                if (errno == EINTR)
                    continue;
                printf("lab05: wait error\n");
                bad = 1;
                break;
            }
            --count;
            /* Decode directly: old 0.11 wait headers have a broken macro. */
            if ((status & 0xff) || ((status >> 8) & 0xff)) {
                printf("lab05: child %d status=%d\n", pid, status);
                bad = 1;
            }
        }
        if (bad)
            break;
    }
    return result(!bad);
}
