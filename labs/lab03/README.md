# 实验三集成约定

## 构建

基线是已恢复72个系统调用的 `vendor/linux-0.11`，与实验一独立，**不要叠加实验一补丁**。复制到 `build/lab03/IMPL/kernel` 后执行 `patch -p1`，再覆盖 `IMPL/kernel/` 到工作副本 `kernel/`。补丁修改系统调用表、构建规则、fork、调度、睡眠/唤醒和退出路径。

将 `IMPL/guest/process.c` 编译为来宾 `/lab/process`，用公共 `tools/guest_build.py`；它通过相对路径包含公共 `guest/trace_user.h`。单文件单可执行程序，不将学生和参考源一起链接。

来宾运行 `/lab/process 15 > /var/lab03.result`，完成后 `sync`。成功标志是 `LAB03 PASS`，并打印 `SELECTED pid1 pid2 pid3`。导出 `/var/process.log` 以及 `/var/lab03.result`，将实际 SELECTED PID 传给：

```bash
python3 tools/trace_stats.py exported-process.log --pids 4 5 6 --json
```

自动化必须从实际输出解析 PID，不能假设固定 PID。还应检查所选进程总体涵盖 N/J/R/W/E（CPU子进程本身不要求有 W），无溢出且生命周期完整。重启独立镜像后以5或30重跑 `/lab/process`，比较两个测量结果。

## 真实内核日志接口

- nr72 `trace_read(char *buffer, unsigned int bytes)`：12字节记录 `{long pid, tick, state}`，i386 little-endian；state为ASCII码，最多32条/调用，返回复制的**字节数**，无数据返回0。bytes必须为12的正整数倍。检查段界限、先 `verify_area`，再在短临界区复制并消费记录。
- nr73 `trace_quantum(int ticks)`：设置调用者基础时间片及当前 counter，范围1..100，返回旧priority；子进程fork继承priority。保留原调度算法的 `counter/2 + priority` 补充规则，**不代表每次固定抢占间隔**。
- 日志8192条，启动 `sched_init` 时开始记录PID0，再记录所有成功fork及状态变化；满后置黏性错误，后续读取一律 `EIO`，必须重新启动。不会悄悄覆盖旧记录。
- 同一进程连续重复状态被去重。同tick事件允许；事件入队与唤醒状态更新使用保存/恢复EFLAGS的中断临界区，适用于单CPU0.11，不支持SMP。
- **仅允许一个约定上的读取者**。接口为共享消费流，未实现每读取者游标或访问控制；不要同时启动多个 `/lab/process`/收集器。

## 对原任务的明确调整

原文要求内核直接维护从启动到关机的 `/var/process.log`。这里内核维护有界内存事件流，来宾父进程把真实事件写到 `/var/process.log`；调度器不调用可能睡眠的文件系统写入。它不是内核直接维护的磁盘文件，也不是无限的全启动日志。首次运行前若8192条未满，可导出启动至测量结束的完整事件；溢出必须作废，重启后及时开始收集。`process`退出后的事件不会继续自动写盘；不能声称涵盖关机。

所有测量只能依赖真实记录；Python的合成测试数据仅验证计算公式，不能充当内核验收证据。学生指导：[实验三](../../docs/lab03.md)。

## 本次验证范围

在当前Ubuntu/WSL2环境中，学生和参考overlay均已通过patch及内核源码编译，来宾C程序通过公共a.out编译链接。统一构建层已实际启动QEMU验证参考实现，日志见对应`build/lab03/reference/`；实验三分别以15和5测量并成功解析真实日志。这些构建产物不作为预置学生答案发布。`manifest.json`记录集成契约，实际入口以根Makefile及`tools/oslab.py`为准。
