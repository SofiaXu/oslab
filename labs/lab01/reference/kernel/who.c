/* Lab 01: user addresses are offsets in the calling task's data segment. */
#include <errno.h>
#include <linux/sched.h>
#include <asm/segment.h>

static char saved_name[24];
static unsigned int saved_length;

int sys_iam(const char *name)
{
    char temporary[24];
    unsigned long address = (unsigned long)name;
    unsigned long limit = get_limit(0x17);
    unsigned int i, j;
    if (!address || address >= limit)
        return -EFAULT;
    /* Read a complete candidate before committing: failure preserves old name. */
    for (i = 0; i < sizeof(temporary); ++i) {
        if (i >= limit - address)
            return -EFAULT;
        temporary[i] = get_fs_byte(name + i);
        if (!temporary[i]) {
            for (j = 0; j <= i; ++j)
                saved_name[j] = temporary[j];
            saved_length = i;
            return i;
        }
    }
    return -EINVAL;
}

int sys_whoami(char *name, unsigned int size)
{
    unsigned int i;
    unsigned long address = (unsigned long)name;
    unsigned long limit = get_limit(0x17);
    if (!address || address >= limit)
        return -EFAULT;
    if (size <= saved_length)
        return -EINVAL;
    if (saved_length + 1 > limit - address)
        return -EFAULT;
    verify_area(name, saved_length + 1);
    for (i = 0; i <= saved_length; ++i)
        put_fs_byte(saved_name[i], name + i);
    return saved_length;
}
