/* Single-CPU Linux 0.11 teaching semaphores: opaque generation-checked IDs.
 * Deliberately NOT POSIX: unlink fails while waiters exist and invalidates IDs.
 */
#include <errno.h>
#include <signal.h>
#include <linux/sched.h>
#include <asm/segment.h>
#define SEM_COUNT 16
#define SEM_NAME 24
#define SEM_MAX 32767
struct semaphore {
    char name[SEM_NAME];
    int id, active, value, nwait;
    struct task_struct *waiters[NR_TASKS];
};
static struct semaphore sems[SEM_COUNT];
static unsigned long lock_sem(void)
{
    unsigned long flags;
    __asm__ volatile("pushfl; popl %0; cli" : "=r"(flags) : : "memory");
    return flags;
}
static void unlock_sem(unsigned long flags)
{
    __asm__ volatile("pushl %0; popfl" : : "r"(flags) : "memory", "cc");
}
static int copy_name(const char *user, char *name)
{
    unsigned long a = (unsigned long)user, limit = get_limit(0x17);
    int i;
    if (!a || a >= limit) return -EFAULT;
    for (i = 0; i < SEM_NAME; ++i) {
        if ((unsigned long)i >= limit - a) return -EFAULT;
        name[i] = get_fs_byte(user + i);
        if (!name[i]) return i ? 0 : -EINVAL;
    }
    return -ENAMETOOLONG;
}
static int equal(const char *a, const char *b)
{
    while (*a && *a == *b) { ++a; ++b; }
    return *a == *b;
}
static struct semaphore *lookup(int id)
{
    struct semaphore *s;
    if (id <= 0) return 0;
    s = &sems[(id - 1) % SEM_COUNT];
    return s->active && s->id == id ? s : 0;
}
int sys_sem_open(const char *name, unsigned int value)
{
    char local[SEM_NAME] = {0};
    int i, j, free_slot = -1, result;
    unsigned long flags;
    result = copy_name(name, local);
    if (result) return result;
    flags = lock_sem();
    for (i = 0; i < SEM_COUNT; ++i) {
        if (sems[i].active && equal(sems[i].name, local)) {
            result = sems[i].id; /* Existing name ignores supplied initial value. */
            unlock_sem(flags); return result;
        }
        if (!sems[i].active && sems[i].id <= 2147483647 - SEM_COUNT)
            free_slot = i;
    }
    if (value > SEM_MAX) { unlock_sem(flags); return -EINVAL; }
    if (free_slot < 0) { unlock_sem(flags); return -ENOSPC; }
    i = free_slot;
    if (!sems[i].id) sems[i].id = i + 1;
    else sems[i].id += SEM_COUNT;
    for (j = 0; j < SEM_NAME; ++j) sems[i].name[j] = local[j];
    sems[i].value = value;
    sems[i].nwait = 0;
    sems[i].active = 1;
    result = sems[i].id;
    unlock_sem(flags);
    return result;
}
static void wake_one(struct semaphore *s)
{
    int i;
    for (i = 0; i < s->nwait; ++i)
        if (s->waiters[i]->state == TASK_INTERRUPTIBLE) {
            s->waiters[i]->state = TASK_RUNNING;
            break;
        }
}
static int interrupted(void)
{
    unsigned long unmaskable = (1UL << (SIGKILL - 1)) | (1UL << (SIGSTOP - 1));
    return current->signal & ~(current->blocked & ~unmaskable);
}
int sys_sem_wait(int id)
{
    struct semaphore *s;
    unsigned long flags = lock_sem();
    int i;
    s = lookup(id);
    if (!s) { unlock_sem(flags); return -EBADF; }
    while (!s->value) {
        if (interrupted()) { unlock_sem(flags); return -EINTR; }
        if (s->nwait >= NR_TASKS) { unlock_sem(flags); return -EAGAIN; }
        s->waiters[s->nwait++] = current;
        current->state = TASK_INTERRUPTIBLE;
        /* IF stays clear through enqueue/state/schedule: no lost wakeup.
         * switch_to loads another task's saved EFLAGS, so it can run with IF=1.
         */
        schedule();
        for (i = 0; i < s->nwait; ++i)
            if (s->waiters[i] == current) break;
        if (i < s->nwait) {
            --s->nwait;
            for (; i < s->nwait; ++i) s->waiters[i] = s->waiters[i + 1];
        }
        if (interrupted()) {
            if (s->value) wake_one(s);
            unlock_sem(flags); return -EINTR;
        }
    }
    --s->value;
    unlock_sem(flags);
    return 0;
}
int sys_sem_post(int id)
{
    struct semaphore *s;
    unsigned long flags = lock_sem();
    s = lookup(id);
    if (!s) { unlock_sem(flags); return -EBADF; }
    if (s->value == SEM_MAX) { unlock_sem(flags); return -ERANGE; }
    ++s->value;
    wake_one(s);
    unlock_sem(flags);
    return 0;
}
int sys_sem_unlink(const char *name)
{
    char local[SEM_NAME] = {0};
    unsigned long flags;
    int i, error = copy_name(name, local);
    if (error) return error;
    flags = lock_sem();
    for (i = 0; i < SEM_COUNT; ++i)
        if (sems[i].active && equal(sems[i].name, local)) {
            if (sems[i].nwait) { unlock_sem(flags); return -EBUSY; }
            sems[i].active = 0;
            unlock_sem(flags); return 0;
        }
    unlock_sem(flags);
    return -ENOENT;
}
