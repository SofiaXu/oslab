#include "lab5.h"
/* TODO_LAB5_SOFTWARE_SWITCH: implement the two linked frames from your diagram.
 * This scaffold deliberately keeps hardware task switching, so the function
 * below is a no-op. Booting it does NOT complete this experiment.
 */
void lab5_init_stack(struct task_struct *p,
    long ebp, long edi, long esi, long gs,
    long ebx, long ecx, long edx, long fs, long es, long ds,
    long eip, long cs, long eflags, long esp, long ss)
{
    (void)p; (void)ebp; (void)edi; (void)esi; (void)gs;
    (void)ebx; (void)ecx; (void)edx; (void)fs; (void)es; (void)ds;
    (void)eip; (void)cs; (void)eflags; (void)esp; (void)ss;
}
