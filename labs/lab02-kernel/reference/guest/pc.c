/* File-backed bounded ring; every file-offset operation is inside mutex. */
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <signal.h>
#include <sys/wait.h>
#include "../../guest/sem_api.h"
struct ring { int in, out, count, expected; int data[10]; };
static int fd, empty, full, mutex;
static void die(const char *what) { perror(what); _exit(2); }
static void down(int s)
{
    while (sem_wait(s) < 0) if (errno != EINTR) die("sem_wait");
}
static void up(int s) { if (sem_post(s)) die("sem_post"); }
static void load(struct ring *b)
{
    if (lseek(fd, 0, 0) != 0 || read(fd, b, sizeof(*b)) != sizeof(*b)) die("buffer read");
}
static void save(struct ring *b)
{
    if (lseek(fd, 0, 0) != 0 || write(fd, b, sizeof(*b)) != sizeof(*b)) die("buffer write");
}
static void produce(int value)
{
    struct ring b;
    down(empty); down(mutex);
    load(&b);
    if (b.count < 0 || b.count >= 10) die("capacity");
    b.data[b.in] = value;
    b.in = (b.in + 1) % 10;
    ++b.count;
    save(&b); up(mutex); up(full);
}
static void consume(void)
{
    struct ring b;
    int value;
    char line[80];
    int n;
    for (;;) {
        down(full); down(mutex);
        load(&b);
        if (b.count <= 0 || b.count > 10) die("capacity");
        value = b.data[b.out];
        b.out = (b.out + 1) % 10;
        --b.count;
        if (value >= 0) {
            if (value != b.expected++) die("order");
            n = sprintf(line, "%d: %d\n", getpid(), value);
            if (write(1, line, n) != n) die("output");
        }
        save(&b); up(mutex); up(empty);
        if (value < 0) _exit(0);
    }
}
int main(int argc, char **argv)
{
    struct ring b = {0};
    int children[8], n = 3, maximum = 500, i, count = 0, status, bad = 0, p;
    if (argc > 1) n = atoi(argv[1]);
    if (argc > 2) maximum = atoi(argv[2]);
    if (n < 2 || n > 8 || maximum < 500 || maximum > 5000) {
        puts("usage: pc [consumers 2..8] [maximum 500..5000]"); return 2;
    }
    sem_unlink("pc.empty"); sem_unlink("pc.full"); sem_unlink("pc.mutex");
    empty = sem_open("pc.empty", 10);
    full = sem_open("pc.full", 0);
    mutex = sem_open("pc.mutex", 1);
    if (empty < 0 || full < 0 || mutex < 0) { perror("sem_open"); return 1; }
    fd = open("/var/pc.buf", O_CREAT | O_TRUNC | O_RDWR, 0600);
    if (fd < 0) die("open buffer");
    save(&b);
    for (i = 0; i < n; ++i) {
        p = fork();
        if (!p) consume();
        if (p < 0) { bad = 1; break; }
        children[count++] = p;
    }
    if (!bad) {
        for (i = 0; i <= maximum; ++i) produce(i);
        for (i = 0; i < count; ++i) produce(-1);
    } else for (i = 0; i < count; ++i) kill(children[i], SIGTERM);
    for (i = 0; i < count; ++i)
        if (waitpid(children[i], &status, 0) < 0 || status) bad = 1;
    load(&b);
    if (b.count || b.expected != maximum + 1) bad = 1;
    close(fd);
    if (sem_unlink("pc.empty")) bad = 1;
    if (sem_unlink("pc.full")) bad = 1;
    if (sem_unlink("pc.mutex")) bad = 1;
    if (unlink("/var/pc.buf")) bad = 1;
    if (bad) { puts("LAB02-PC FAIL"); return 1; }
    puts("LAB02-PC PASS");
    return 0;
}
