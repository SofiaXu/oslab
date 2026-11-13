# 实验五集成约定

学生指导：[用内核栈完成进程切换](../../docs/lab05.md)。实验独立于一、三，不叠加其他实验补丁。

- 公共 `kernel.patch` 对移植基线执行 `patch -p1`；再复制 `student/kernel/` 或 `reference/kernel/` 到工作副本的 `kernel/`。主工具自动处理，正常使用 `make lab5`、`make run-lab5`、`make check-lab5`，可选 `IMPL=reference`。
- 工作区：`build/lab05/{student,reference}/kernel`。补丁不修改 `Makefile.header`；继承基线 i386/GCC13 选项，特别是 `-march=i386`、无 PIE/PIC、无优化、4 字节栈对齐。无需额外汇编工具。
- `lab5_switch.S` 为 i386 cdecl，`lab5_offsets.c` 在编译期生成偏移；新增 PCB 字段只在末尾。软件路径保留启动 TSS 的 TR、更新其 esp0；重载 LDT 后恢复段缓存；保存/恢复 IF 并手动管理 CR0.TS。孩子的 88 字节初始帧通过 `lab5_fork_return` 接到 `ret_from_sys_call`。
- `guest_test.c` 用 `python3 tools/guest_build.py labs/lab05/guest_test.c build/lab05/reference/guest/lab05_test` 构建。主工具安装到私有磁盘 `rootfs.img` 的 `/lab/lab05_test`。不链接宿主 glibc，不依赖浮点运行库；x87 验证用显式指令。
- 来宾执行 `/lab/lab05_test`，预期正常退出且 stdout 和 `/var/lab05.result` 最终出现 `LAB05_PASS`。初始输出为 `LAB05_RUNNING`，失败为 `LAB05_FAIL`；不能读取上次运行残留的 PASS。可用 `/lab/lab05_test 12 120000` 加长压力测试；应正常 fork/wait 并继续使用 shell。
- 学生骨架故意使用硬件切换，能编译、启动，甚至可能通过来宾行为探针。必须拒绝未移除的 `TODO_LAB5_SOFTWARE_SWITCH`，并检查实际编译对象，防止仅删标记放行。C 的 `lab5_init_stack` 也是必做 TODO。AI 生成汇编、审查和调试记录是必交材料。

```bash
python3 tests/test_stack_layout.py -v
python3 tests/test_stack_layout.py --check-switch build/lab05/reference/kernel/kernel/lab5_switch.o
```

第一条是在临时副本上的参考/骨架回归；学生发布包不含 reference 时整组明确跳过。第二条可独立检查任意已构建的学生或参考对象，无须参考目录：拒绝 `ljmp/lcall/ltr`，核对 ESP 保存/装载、LDT、IF、TS 的结构，不替代 QEMU 语义验证。主集成器可调用第二条命令作为对象门禁，非零退出即拒绝验收。

验证记录：参考和学生 `kernel.o` 已通过 GCC13 编译链接，i386 无 libc 帧构造测试通过，删除 TODO 的硬件骨架仍被对象门禁拒绝。主集成流程已在 QEMU 8.2、`-cpu 486` 和 `-march=i386` 下确认参考内核启动、shell、`LAB05_PASS` 与退出码 0。未把宿主静态测试当作来宾运行证据。
