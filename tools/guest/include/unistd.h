#ifndef OSLAB_UNISTD_H
#define OSLAB_UNISTD_H
#include <sys/types.h>
#define STDIN_FILENO 0
#define STDOUT_FILENO 1
#define STDERR_FILENO 2
#define SEEK_SET 0
#define SEEK_CUR 1
#define SEEK_END 2
int read(int, void *, unsigned);
int write(int, const void *, unsigned);
int close(int);
int open(const char *, int, ...);
off_t lseek(int, off_t, int);
pid_t fork(void);
pid_t getpid(void);
pid_t getppid(void);
int pipe(int *);
int dup(int);
int dup2(int, int);
int unlink(const char *);
int chdir(const char *);
int execve(const char *, char *const[], char *const[]);
int pause(void);
unsigned alarm(unsigned);
unsigned sleep(unsigned);
int usleep(unsigned);
void sync(void);
void _exit(int) __attribute__((noreturn));
long syscall(long, ...);
#endif
