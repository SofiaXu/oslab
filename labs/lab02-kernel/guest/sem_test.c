#include <stdio.h>
#include <unistd.h>
#include <sys/wait.h>
#include "sem_api.h"
static int bad;
static void check(int yes, const char *what)
{ if (!yes) { printf("FAIL %s errno=%d\n", what, errno); ++bad; } }
int main(void)
{
    int s, again, child, status, got;
    sem_unlink("gate");
    s = sem_open("gate", 0);
    check(s > 0, "create zero semaphore");
    if (s <= 0) return 1;
    check(sem_open("gate", 7) == s, "open existing ignores value");
    check(sem_wait(-1) == -1 && errno == EBADF, "invalid handle");
    check(sem_open((char *)0, 0) == -1 && errno == EFAULT, "NULL name");
    check(sem_open("123456789012345678901234", 0) == -1 && errno == ENAMETOOLONG, "long name");
    child = fork();
    if (!child) { if (sem_wait(s)) _exit(2); _exit(0); }
    if (child < 0) { perror("fork"); sem_unlink("gate"); return 1; }
    sleep(1);
    got = waitpid(child, &status, WNOHANG);
    check(got == 0, "wait actually blocks");
    check(sem_unlink("gate") == -1 && errno == EBUSY, "cannot unlink queued semaphore");
    check(sem_post(s) == 0, "post wakes blocked child");
    if (!got) {
        got = waitpid(child, &status, 0);
        check(got == child && status == 0, "child acquired token and exited");
    }
    check(sem_unlink("gate") == 0, "unlink");
    again = sem_open("gate", 1);
    check(again > 0 && again != s, "generation changes after reuse");
    check(sem_post(s) == -1 && errno == EBADF, "stale handle rejected");
    check(sem_wait(again) == 0, "initial value");
    check(sem_unlink("gate") == 0, "cleanup");
    if (bad) { puts("LAB02-KERNEL FAIL"); return 1; }
    puts("LAB02-KERNEL PASS");
    return 0;
}
