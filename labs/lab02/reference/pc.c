#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <semaphore.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

/* No shared pointers: mmap's file contains only the ring and its indices. */
#define CAPACITY 10
#define MAX_CONSUMERS 128
struct ring { unsigned head, tail, count; int slots[CAPACITY]; };
static volatile sig_atomic_t interrupted;
static void on_signal(int sig) { interrupted = sig; }
static int down(sem_t *s)
{
    for (;;) {
        if (interrupted) { errno = EINTR; return -1; }
        if (!sem_wait(s)) return 0;
        if (errno != EINTR) return -1;
    }
}
static int emit(int value)
{
    char line[80];
    int size = snprintf(line, sizeof line, "%ld:%d\n", (long)getpid(), value);
    int offset = 0;
    while (offset < size) {
        ssize_t n = write(STDOUT_FILENO, line + offset, (size_t)(size - offset));
        if (n < 0 && errno == EINTR && !interrupted) continue;
        if (n <= 0) return -1;
        offset += (int)n;
    }
    return 0;
}
static int produce(struct ring *r, sem_t **s, int maximum, int unsafe)
{
    for (int value = 0; value <= maximum; ++value) {
        if (down(s[0]) || (!unsafe && down(s[2]))) return -1;
        if (!unsafe && r->count >= CAPACITY) return -1;
        r->slots[r->tail] = value;
        r->tail = (r->tail + 1) % CAPACITY;
        if (!unsafe) ++r->count;
        if ((!unsafe && sem_post(s[2])) || sem_post(s[1])) return -1;
    }
    return 0;
}
static int consume(struct ring *r, sem_t **s, int quota, int unsafe)
{
    for (int i = 0; i < quota; ++i) {
        if (down(s[1]) || (!unsafe && down(s[2]))) return -1;
        if (!unsafe && !r->count) return -1;
        unsigned head = r->head;
        /* Widen the deliberately broken read/modify/write window for comparison. */
        if (unsafe) {
            struct timespec delay = {0, 100000};
            nanosleep(&delay, NULL);
        }
        int value = r->slots[head];
        r->head = (head + 1) % CAPACITY;
        if (!unsafe) --r->count;
        /* Printing belongs inside the same critical section as removal. */
        if (emit(value)) return -1;
        if ((!unsafe && sem_post(s[2])) || sem_post(s[0])) return -1;
    }
    return 0;
}
static int number(const char *text, int min, int max, int *out)
{
    char *end;
    errno = 0;
    long n = strtol(text, &end, 10);
    if (errno || !*text || *end || n < min || n > max) return -1;
    *out = (int)n;
    return 0;
}
static void usage(FILE *out)
{
    fprintf(out, "Usage: pc [--consumers N (2..128)] [--max M (500..2147483646)]\n"
                 "          [--file NEW_PATH] [--unsafe]\n"
                 "Defaults: N=3 M=500; temporary file is removed on exit.\n");
}
int main(int argc, char **argv)
{
    int consumers = 3, maximum = 500, unsafe = 0, fd = -1, owned = 0, rc = 1;
    const char *path = NULL;
    char temporary[] = "/tmp/oslab-pc-XXXXXX";
    sem_t *s[3] = {SEM_FAILED, SEM_FAILED, SEM_FAILED};
    char names[3][96] = {{0}};
    int created[3] = {0};
    struct ring *r = MAP_FAILED;
    pid_t children[MAX_CONSUMERS + 1];
    int live = 0;
    for (int i = 1; i < argc; ++i) {
        if (!strcmp(argv[i], "--help")) { usage(stdout); return 0; }
        if (!strcmp(argv[i], "--unsafe")) { unsafe = 1; continue; }
        if (!strcmp(argv[i], "--consumers") && i + 1 < argc) {
            if (number(argv[++i], 2, MAX_CONSUMERS, &consumers)) goto invalid;
        } else if (!strcmp(argv[i], "--max") && i + 1 < argc) {
            if (number(argv[++i], 500, INT_MAX - 1, &maximum)) goto invalid;
        } else if (!strcmp(argv[i], "--file") && i + 1 < argc) path = argv[++i];
        else goto invalid;
    }
    struct sigaction action;
    memset(&action, 0, sizeof action);
    sigemptyset(&action.sa_mask);
    action.sa_handler = on_signal;
    if (sigaction(SIGINT, &action, NULL) || sigaction(SIGTERM, &action, NULL) ||
        sigaction(SIGHUP, &action, NULL)) { perror("sigaction"); return 1; }
    /* Broken output pipes become errors, not an unobserved signal death. */
    action.sa_handler = SIG_IGN;
    if (sigaction(SIGPIPE, &action, NULL)) { perror("sigaction"); return 1; }
    if (path) fd = open(path, O_RDWR | O_CREAT | O_EXCL, 0600);
    else { fd = mkstemp(temporary); path = temporary; }
    if (fd < 0) { perror("create ring file (must not exist)"); goto cleanup; }
    owned = 1;
    if (ftruncate(fd, sizeof *r)) { perror("ftruncate"); goto cleanup; }
    r = mmap(NULL, sizeof *r, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (r == MAP_FAILED) { perror("mmap"); goto cleanup; }
    memset(r, 0, sizeof *r);
    struct timespec now;
    if (clock_gettime(CLOCK_MONOTONIC, &now)) { perror("clock_gettime"); goto cleanup; }
    for (int i = 0; i < 3; ++i) {
        snprintf(names[i], sizeof names[i], "/oslab_pc_%lu_%ld_%ld_%d",
                 (unsigned long)getuid(), (long)getpid(), now.tv_nsec, i);
        s[i] = sem_open(names[i], O_CREAT | O_EXCL, 0600, i == 0 ? CAPACITY : i == 1 ? 0 : 1);
        if (s[i] == SEM_FAILED) { perror("sem_open"); goto cleanup; }
        created[i] = 1;
    }
    /* Resource names aid independent cleanup verification, never mix with stdout. */
    fprintf(stderr, "RESOURCES file=%s empty=%s full=%s mutex=%s\n", path, names[0], names[1], names[2]);
    fflush(stderr);
    for (int i = 0; i <= consumers; ++i) {
        if (interrupted) goto cleanup;
        pid_t pid = fork();
        if (pid < 0) { perror("fork"); goto cleanup; }
        if (!pid) {
            int result;
            if (!i) result = produce(r, s, maximum, unsafe);
            else {
                /* Exact quotas avoid poison pills and total-count ambiguity. */
                int quota = (maximum + 1) / consumers + (i <= (maximum + 1) % consumers);
                result = consume(r, s, quota, unsafe);
            }
            for (int j = 0; j < 3; ++j) sem_close(s[j]);
            munmap(r, sizeof *r);
            close(fd);
            _exit(result ? 1 : 0);
        }
        children[live++] = pid;
    }
    while (live && !interrupted) {
        int status;
        pid_t pid = waitpid(-1, &status, WNOHANG);
        if (pid > 0) {
            for (int i = 0; i < live; ++i)
                if (children[i] == pid) { children[i] = children[--live]; break; }
            if (!WIFEXITED(status) || WEXITSTATUS(status)) {
                fprintf(stderr, "Child %ld failed (wait status %d); cancelling peers\n", (long)pid, status);
                goto cleanup;
            }
        } else if (pid < 0 && errno != EINTR) { perror("waitpid"); goto cleanup; }
        else {
            /* Polling closes the signal-before-wait race; no SA_RESTART reliance. */
            struct timespec delay = {0, 10000000};
            nanosleep(&delay, NULL);
        }
    }
    if (!interrupted) rc = 0;
cleanup:
    /* A dead child may own mutex: terminate peers, never wait for that lock. */
    for (int i = 0; i < live; ++i) kill(children[i], SIGKILL);
    for (int i = 0; i < live; ++i)
        while (waitpid(children[i], NULL, 0) < 0 && errno == EINTR) {}
    for (int i = 0; i < 3; ++i) {
        if (s[i] != SEM_FAILED && sem_close(s[i])) { perror("sem_close"); rc = 1; }
        if (created[i] && sem_unlink(names[i])) { perror("sem_unlink"); rc = 1; }
    }
    if (r != MAP_FAILED && munmap(r, sizeof *r)) { perror("munmap"); rc = 1; }
    if (fd >= 0 && close(fd)) { perror("close"); rc = 1; }
    if (owned && unlink(path)) { perror("unlink"); rc = 1; }
    return interrupted ? 128 + interrupted : rc;
invalid:
    usage(stderr);
    return 2;
}
