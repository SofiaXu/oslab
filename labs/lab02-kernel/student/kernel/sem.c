#include <errno.h>
/* TODO: bounded table, checked opaque IDs, saved/restored IRQ flags, wait queue.
 * Never hold a pointer into user memory while sleeping.
 */
int sys_sem_open(const char *name, unsigned int value)
{ (void)name; (void)value; return -ENOSYS; }
int sys_sem_wait(int id)
{ (void)id; return -ENOSYS; }
int sys_sem_post(int id)
{ (void)id; return -ENOSYS; }
int sys_sem_unlink(const char *name)
{ (void)name; return -ENOSYS; }
