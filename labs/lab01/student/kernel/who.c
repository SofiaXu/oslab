#include <errno.h>
/* TODO: get_limit/get_fs_byte read a candidate (23 bytes + NUL), then commit. */
int sys_iam(const char *name)
{
    (void)name;
    return -ENOSYS;
}
/* TODO: check pointer/size, verify_area, put_fs_byte; return length without NUL. */
int sys_whoami(char *name, unsigned int size)
{
    (void)name;
    (void)size;
    return -ENOSYS;
}
