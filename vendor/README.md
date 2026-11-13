# 固定的 Linux 0.11 教学基线

上游仓库、提交、根文件系统 URL 与 SHA-256 统一记录在 [sources.json](sources.json)。
源码已直接纳入仓库，不需要 submodule 或上游分支，也不依赖教师电脑。
`linux-0.11.sha256` 记录此教学基线每个文件的校验值。

相对固定上游提交的变化：

1. 删除上游夹带的实验一 `kernel/who.c` 答案与系统调用注册，恢复为 72 个系统调用。各实验独立添加自己的调用，不串接实验补丁。
2. 内核明确使用 GCC 的 gnu89、i386 指令集、非 PIE/PIC、无 SSE/MMX、4 字节栈对齐与无优化构建。原版汇编接口不能套用现代 16 字节栈约定；显式 i386 也避免在模拟 486 时生成 CMOV。
3. 将上游启动文字改为 Linux 0.11。根文件系统独立下载，不把镜像或上游附带的宿主 GDB 二进制混入源码。
4. 保留上游其余移植代码。与这些文件对应的文本差异记录在 `patches/teaching-baseline.patch`；被删除的答案文件仅记录文件名，不在补丁中再次分发答案。

校验命令（Ubuntu，仓库根目录）：

```bash
(cd vendor/linux-0.11 && sha256sum -c ../linux-0.11.sha256)
```

不要在这里完成实验。工具把基线复制到 `build/labNN/IMPL/kernel`，再应用相应实验补丁和学生/参考文件。关于第三方条款见 [THIRD_PARTY.md](../THIRD_PARTY.md)。
