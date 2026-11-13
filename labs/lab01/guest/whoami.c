#include <stdio.h>
#include "lab01_api.h"
int main(void)
{
    char name[24];
    if (whoami(name, sizeof(name)) < 0) { perror("whoami"); return 1; }
    puts(name);
    return 0;
}
