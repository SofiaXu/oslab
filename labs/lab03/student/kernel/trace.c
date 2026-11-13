#include <errno.h>
#include <linux/sched.h>
#include "trace.h"
/* TODO: interrupt-safe bounded ring. Do not write files in schedule/wake_up. */
void trace_event(struct task_struct *p, int state)
{
    (void)p; (void)state;
}
void trace_set_state(struct task_struct *p, long state)
{
    /* Preserve scheduler functionality while implementing the log. */
    p->state = state;
    /* TODO: append J/W/E atomically with assignment. */
}
int sys_trace_read(char *buffer, unsigned int bytes)
{
    (void)buffer; (void)bytes;
    return -ENOSYS;
}
int sys_trace_quantum(int ticks)
{
    (void)ticks;
    return -ENOSYS;
}
