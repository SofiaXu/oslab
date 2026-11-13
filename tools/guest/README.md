# Linux 0.11 来宾程序构建

宿主 Ubuntu 的 ELF/glibc 程序不能直接在 Linux 0.11 中运行。本目录提供一个可读的小型运行库，配合宿主 apt 安装的 GCC/binutils，生成内核接受的 i386 ZMAGIC a.out：

```bash
python3 tools/guest_build.py labs/lab01/guest/iam.c build/iam
```

输出 `build/iam` 是来宾程序，`build/iam.elf` 保留调试符号。工具用自定义链接脚本，从 ELF 中取 text/data/bss 和入口，再写 1024 字节 a.out 头部区域。`start.S` 根据 **0.11** 的 `argc, argv 指针, envp 指针` 栈布局调用 `main`，不是现代 ELF 入口约定。系统调用通过 `int $0x80` 完成。

这是教学运行库，不是 glibc 的替代品：

- 无动态链接、线程或完整 POSIX；`stdio` 不缓存，格式化只支持本套件使用的整数、字符串和字符，不支持浮点格式。
- `malloc` 是最多 128 KiB 的单调分配器，`free` 不回收；只适合短生命周期实验程序。
- `sleep` 使用历史 alarm/signal，只适合没有其他并发定时器的实验负载；`usleep` 向上取整为秒，不提供亚秒精度。
- 头文件使用历史内核 ABI，不能混入 `/usr/include` 的现代结构体定义。
- 本套件的内核扩展都有专用的调用包装器，不要求学生编写通用汇编运行库。

原生 Ubuntu 实验使用系统 libc，不受这些限制。需要一般用户程序开发时，可使用镜像内的历史编译环境，但这不是默认构建路径。
