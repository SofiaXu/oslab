# 实验一集成约定

本目录只包含 Linux 0.11 的真实系统调用补丁，不提供宿主模拟替代品。

- 基线：`vendor/linux-0.11`，已移除上游 `who.c` 和两个额外系统调用；系统调用总数为 72。现代 GCC 兼容修订由公共构建层负责。
- 先复制基线到 `build/lab01/IMPL/kernel`，在该目录执行 `patch -p1 < labs/lab01/IMPL/kernel.patch`（使用绝对路径），然后把 `IMPL/kernel/` 内容覆盖到工作副本的 `kernel/`。
- 构建层必须将学生、参考实现的源码与磁盘隔离；不要原地修改 vendor。
- `guest/*.c` 均是独立可执行程序，使用 `tools/guest_build.py`，安装来宾路径 `/lab/iam`、`/lab/whoami`、`/lab/lab01_test`，权限 0755。程序无需宿主 libc，inline `int 0x80` 包装已提供。
- 推荐验收命令：来宾 `/lab/lab01_test > /var/lab01.result`，之后 `sync`；导出结果应包含 `LAB01 PASS`，且不得含 `FAIL`。学生初始版本必须失败，内核返回 `-ENOSYS`。

| 编号 | 内核接口 | 结果 |
| --- | --- | --- |
| 72 | `sys_iam(const char *name)` | 保存最多23字节，返回不含 NUL 的长度 |
| 73 | `sys_whoami(char *buffer, unsigned int size)` | 写入含 NUL 的字符串，返回不含 NUL 的长度 |

空姓名有效。空指针及越过数据段边界返回 `EFAULT`；姓名超过23字节、输出空间不足返回 `EINVAL`。先检查指针，再检查长度。输出空间 `size` 包含末尾 NUL。共享姓名为内核全局状态，重启清空、进程间共享；0.11 不抢占正在运行的内核代码，本实现不支持 SMP。

分段界限验证不等同于现代内核的 `copy_from_user` 异常恢复机制；这里遵循 0.11 的按需分页和 `verify_area` 约定。不得把宿主地址或任意内核指针传给此接口。

学生指导：[实验一](../../docs/lab01.md)。

## 本次验证范围

在当前Ubuntu/WSL2环境中，学生和参考overlay均已通过patch及内核源码编译，来宾C程序通过公共a.out编译链接。统一构建层已实际启动QEMU验证参考实现，日志见对应`build/lab01/reference/`；验收输出含上述PASS标志及0退出状态。这些构建产物不作为预置学生答案发布。`manifest.json`记录集成契约，实际入口以根Makefile及`tools/oslab.py`为准。
