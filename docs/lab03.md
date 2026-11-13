# 实验三：用真实进程轨迹解释调度结果

> 完整仓库包含独立参考实现；学生发布包不含 `reference/`。学生包中跳过参考演示，完成代码后使用默认的 `make check-lab3` 验收自己的实现。

你会在Linux 0.11内核记录进程状态，在来宾运行多个子进程，再用Python计算等待、运行、阻塞和周转时间。最终结论必须来自自己的真实日志，不能以预先画好的状态图代替内核实现。

## 1. 任务、环境和日志方案

先完成[环境准备](setup-wsl2.md)，并熟悉`fork`、`waitpid`和文件读写；可先读[C与进程补充知识](prerequisites.md)。所有`make`和Python命令在**仓库根目录、Ubuntu终端**执行：

```bash
make doctor
make prepare
make lab3
make check-lab3
```

学生骨架能构建但没有完成日志和负载，自检失败符合预期。要先观察完整参考结果：

```bash
make check-lab3 IMPL=reference
```

检查会分别从独立磁盘启动基础时间片15和5的两次测量。结果在`build/lab03/reference/`：`result-15.txt`、`process-15.log`、`stats-15.json`及相应的`-5`文件。学生路径对应为`build/lab03/student/`，内核源码副本为`kernel/`。

**与原实验要求的明确差异：**原文要求内核直接把从启动到关机的所有轨迹写到`/var/process.log`。本套件内核从启动开始记录到8192条的内存环形缓冲区，由来宾父进程在测量期间读取真实事件并写入该文件。调度器不进行可能阻塞的磁盘写入。因此它是“内核产生事件、用户程序导出”的有限窗口方案，**不是内核直接维护的全启动至关机磁盘日志**。程序退出后没有常驻收集daemon，后续事件不会自动写盘。缓冲区满后读取返回`EIO`，整次测量必须作废并重启；禁止静默覆盖或补造丢失事件。启动后应及时开始收集，且一次只能运行一个收集程序。

## 2. 五种状态与内核位置

每条日志格式为`PID<TAB>状态<TAB>tick`：

| 状态 | 含义 | 记录时机 |
| --- | --- | --- |
| N | 新建 | 成功fork、子进程资源准备完成 |
| J | 就绪 | 新进程可运行、阻塞进程唤醒或运行进程让出CPU |
| R | 运行 | 调度器选择它执行 |
| W | 阻塞 | 调用睡眠、pause或等待子进程等 |
| E | 退出 | 完成退出清理后成为僵尸进程 |

`tick`是内核`jiffies`，此基线`HZ=100`，100tick约一秒。不是日期时间；同tick可以有多个状态变化。E到父进程回收僵尸的时间不计入周转时间。PID0为空闲任务，不参与负载统计。

Linux0.11把就绪与正在运行都表示为`TASK_RUNNING`；J/R的区别要靠调度事件辨别，不能仅打印`task->state`。文件访问命中缓存不一定阻塞，所以负载必须显式包含`sleep(1)`型任务以观察W。

已提供的学生patch连接`fork.c`、`sched.c`、`exit.c`的入口。逐处核对它们覆盖的睡眠、普通唤醒、信号唤醒及退出路径，注意`wake_up`还会在中断上下文被调用。不能无条件`sti()`；要保存、关闭并恢复原中断状态。状态赋值与对应事件应在同一短临界区完成。临界区内不得文件写入、打印、大量分配或睡眠；用户缓冲区的`verify_area`也在进入临界区前完成。

## 3. 完成学生代码

学生目录为`labs/lab03/student/`。公共`guest/trace_user.h`提供了系统调用包装、完整写入及导出工具；inline汇编可直接使用。

1. 在`kernel/trace.c`实现有界事件队列和`trace_event`，记录原始PID、tick、状态。对连续相同状态去重；中断保护应兼容已关闭中断的调用环境。
2. 实现`trace_set_state`，原子更新状态并按变化生成J/W/E；不要破坏原调度语义。排队过程不应修改调度算法。
3. 实现nr72的`sys_trace_read`：输入缓冲区及字节容量，输出12字节记录`{long pid,tick,state}`，最多32条/次，返回字节数；无记录返回0，容量不是12的正整数倍返回`EINVAL`，坏范围`EFAULT`，溢出`EIO`。
4. 实现nr73的`sys_trace_quantum`，将调用者priority和counter设置到1..100，返回原priority，非法值返回`EINVAL`。fork会继承priority。
5. 完成`guest/process.c`：至少三个并行子进程，包含CPU忙循环和sleep负载，各自实际运行少于30秒。父进程打印每个PID、定期导出、等待全部子进程并检查退出状态。成功才打印`LAB03 PASS`；统计对象以`SELECTED pid1 pid2 pid3`一行标明。
6. 用`make check-lab3`执行两次真实QEMU测量。失败时先看同一目录的`build.log`、`screen-15.txt`和`result-15.txt`，再检查日志。

建议主要编辑overlay；临时在`build/lab03/student/kernel`调试的修改要整理回学生patch/overlay提交。学生与参考实现各有独立内核和`rootfs.img`，不要把实验一补丁再叠加到实验三：这里72、73已用于日志接口。

## 4. 运行与统计

交互运行：

```bash
make run-lab3
```

在**0.11来宾shell**执行：

```sh
/lab/process 15 > /var/lab03.result
cat /var/lab03.result
sync
```

记录实际`SELECTED`的PID。退出QEMU、确认磁盘不再被使用后，在Ubuntu导出交互磁盘中的日志：

```bash
python3 tools/minix.py build/lab03/student/rootfs.img get /var/process.log /tmp/my-process.log
python3 tools/trace_stats.py /tmp/my-process.log --pids 4 5 6 --json
```

这里的4、5、6仅为命令示例，必须换成自己输出中的PID。不要从Ubuntu的`ps`获取它们。自动检查使用另外的`check-15.img`/`check-5.img`，不修改交互磁盘；例如重新导出参考自动验收日志：

```bash
python3 tools/minix.py build/lab03/reference/check-15.img get /var/process.log /tmp/checked-process.log
```

自动生成的`process-15.log`已经是同一个文件的导出副本。检查镜像和交互镜像不可混用；QEMU运行时不得离线读写镜像。

手算练习：一个进程依次经历`N0 J0 R2 W5 J9 R10 E14`。运行时间为`(5-2)+(14-10)=7`tick；就绪等待为`(2-0)+(10-9)=3`；阻塞为`9-5=4`；周转为`14-0=14`。这里三类之和等于周转；若N到J跨tick，另列创建时间补足。

统计工具会拒绝选中PID缺N或E、状态跳跃、重复事件、倒退tick和溢出标记，不对缺失区间猜测。后台shell/init可以只有部分生命周期，但**被选中的负载进程必须完整**。输出含逐PID运行/就绪/阻塞/创建/周转tick及均值。吞吐量的区间统一为“所选进程最早N到最晚E”，单位进程/秒；同tick结束的零时长区间输出null，不生成无穷值。

## 5. 时间片对比、验收与报告

`/lab/process 5`把父进程的基础时间片设为5，孩子继承。它不改全局所有进程；原调度器仍用`counter/2 + priority`补充时间，所以实际运行段未必总是5tick。不要把priority直接解释为现代调度器的静态优先级。

自动检查在两次新启动中运行相同负载，减少已有进程和资源状态的干扰。比较`stats-15.json`与`stats-5.json`，报告每个PID及平均就绪时间、周转时间、吞吐量。PID可不同，按CPU/阻塞负载角色比较；tick和模拟器速度也可能波动。不能预先断言“小时间片总更快”。

验收要求：三个孩子确实并行、父进程全部等待、所选轨迹总体覆盖N/J/R/W/E、生命周期完整、无丢失、两次时间片设置有效，导出与统计可复核。日志中有五种字母不等于每个孩子都必须阻塞。`tests/test_trace.py`只测试计算公式，其合成数据不是本实验的真实运行证据。

提交patch及overlay源码、两次原始日志和PID清单、统计JSON、来宾运行截图、报告及AI使用记录。评分100分：多进程负载30、真实内核状态记录与安全导出30、统计及完整性验证15、时间片对比10、报告与思考题15。

保留原思考题：从程序设计者角度，单进程与多进程编程最大的区别是什么？你怎样修改时间片，修改前后所选进程的统计结果是什么，为什么变化或不变？另外解释：为什么不能直接在`schedule()`调用普通文件写函数？发生溢出后为何必须放弃该测量，而不能只删掉异常行？

接口和限制的完整清单见[实验目录说明](../labs/lab03/README.md)。
