#ifndef LAB_TRACE_H
#define LAB_TRACE_H
struct task_struct;
void trace_event(struct task_struct *p, int state);
void trace_set_state(struct task_struct *p, long state);
#endif
