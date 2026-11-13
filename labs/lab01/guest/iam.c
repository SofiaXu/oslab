#include <stdio.h>
#include "lab01_api.h"
int main(int argc, char **argv)
{
    int n;
    if (argc != 2) { puts("usage: iam NAME"); return 2; }
    n = iam(argv[1]);
    if (n < 0) { perror("iam"); return 1; }
    printf("saved %d bytes\n", n);
    return 0;
}
