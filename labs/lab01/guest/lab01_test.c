#include <stdio.h>
#include <string.h>
#include "lab01_api.h"
static int errors;
static void check(int yes, const char *what)
{
    if (!yes) { printf("FAIL: %s errno=%d\n", what, errno); ++errors; }
}
int main(void)
{
    char out[32];
    char exact[] = "12345678901234567890123";
    char longer[] = "123456789012345678901234";
    check(iam("Alice") == 5, "iam normal");
    check(whoami(out, sizeof(out)) == 5 && !strcmp(out, "Alice"), "round trip");
    check(iam(exact) == 23, "23 accepted");
    check(iam(longer) == -1 && errno == EINVAL, "24 rejected");
    check(whoami(out, 24) == 23 && !strcmp(out, exact), "failed iam preserves value");
    strcpy(out, "sentinel");
    check(whoami(out, 23) == -1 && errno == EINVAL, "size needs NUL");
    check(!strcmp(out, "sentinel"), "short buffer unchanged");
    check(whoami(out, 0) == -1 && errno == EINVAL, "zero capacity");
    check(iam((char *)0) == -1 && errno == EFAULT, "NULL input");
    check(whoami((char *)0, 32) == -1 && errno == EFAULT, "NULL output");
    check(iam((char *)0xffffffffUL) == -1 && errno == EFAULT, "segment bound read");
    check(whoami((char *)0xffffffffUL, 32) == -1 && errno == EFAULT, "segment bound write");
    check(iam("") == 0, "empty name");
    check(whoami(out, 1) == 0 && out[0] == 0, "empty NUL");
    if (errors) { printf("LAB01 FAIL %d\n", errors); return 1; }
    puts("LAB01 PASS");
    return 0;
}
