/* No filesystem calls, printk, sleep, or memory allocation in event producer. */
#include <errno.h>
#include <linux/sched.h>
#include <asm/segment.h>
#include "trace.h"

#define TRACE_CAPACITY 8192
#define TRACE_BATCH 32
struct trace_record { long pid, tick, state; };
static struct trace_record events[TRACE_CAPACITY];
static unsigned int head, tail, count;
static int lost;
static long previous_pid[NR_TASKS];
static int previous_state[NR_TASKS];

/* Save/restore IF: wake_up may run in interrupt context with IF already clear. */
static unsigned long lock_trace(void)
{
    unsigned long flags;
    __asm__ volatile ("pushfl; popl %0; cli" : "=r" (flags) : : "memory");
    return flags;
}
static void unlock_trace(unsigned long flags)
{
    __asm__ volatile ("pushl %0; popfl" : : "r" (flags) : "memory", "cc");
}
static void append(struct task_struct *p, int state)
{
    int slot;
    for (slot = 0; slot < NR_TASKS; ++slot)
        if (task[slot] == p) break;
    if (slot < NR_TASKS) {
        if (previous_pid[slot] == p->pid && previous_state[slot] == state)
            return;
        previous_pid[slot] = p->pid;
        previous_state[slot] = state;
    }
    if (count == TRACE_CAPACITY) {
        lost = 1; /* Sticky: incomplete measurements must never look successful. */
        return;
    }
    events[head].pid = p->pid;
    events[head].tick = jiffies;
    events[head].state = state;
    head = (head + 1) % TRACE_CAPACITY;
    ++count;
}
void trace_event(struct task_struct *p, int state)
{
    unsigned long flags = lock_trace();
    append(p, state);
    unlock_trace(flags);
}
void trace_set_state(struct task_struct *p, long state)
{
    unsigned long flags = lock_trace();
    if (p->state != state) {
        p->state = state;
        append(p, state == TASK_RUNNING ? 'J' :
                  state == TASK_ZOMBIE ? 'E' : 'W');
    }
    unlock_trace(flags);
}

/* nr72: copies whole 12-byte records; nonblocking, max 32 per call.
 * Exactly one userspace collector must drain the shared stream.
 * verify_area is outside critical section (COW faults may allocate/sleep).
 */
int sys_trace_read(char *buffer, unsigned int bytes)
{
    unsigned long address = (unsigned long)buffer, limit = get_limit(0x17);
    unsigned long flags;
    unsigned int n, i;
    if (!address || address >= limit)
        return -EFAULT;
    if (!bytes || bytes % sizeof(struct trace_record))
        return -EINVAL;
    n = bytes / sizeof(struct trace_record);
    if (n > TRACE_BATCH)
        n = TRACE_BATCH;
    if (n * sizeof(struct trace_record) > limit - address)
        return -EFAULT;
    verify_area(buffer, n * sizeof(struct trace_record));
    flags = lock_trace();
    if (lost) {
        unlock_trace(flags);
        return -EIO;
    }
    if (n > count)
        n = count;
    for (i = 0; i < n; ++i) {
        put_fs_long(events[tail].pid, (unsigned long *)(buffer + i * 12));
        put_fs_long(events[tail].tick, (unsigned long *)(buffer + i * 12 + 4));
        put_fs_long(events[tail].state, (unsigned long *)(buffer + i * 12 + 8));
        tail = (tail + 1) % TRACE_CAPACITY;
        --count;
    }
    unlock_trace(flags);
    return n * sizeof(struct trace_record);
}

/* nr73: set caller's base quantum (inherited by fork), not a global policy. */
int sys_trace_quantum(int ticks)
{
    int old = current->priority;
    if (ticks < 1 || ticks > 100)
        return -EINVAL;
    current->priority = ticks;
    current->counter = ticks;
    return old;
}
