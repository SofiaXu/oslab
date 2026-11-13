# 实验二选做：Linux 0.11 内核信号量

本扩展与实验一、三采用**各自干净的72调用基线**，不可直接叠加补丁；与 Ubuntu POSIX `sem_t *` 不是相同ABI。

## 构建与验收入口

在仓库根目录执行`make lab2-kernel`、`make run-lab2-kernel`、`make check-lab2-kernel`；默认student，可加`IMPL=reference`查看参考运行。独立CLI为`python3 tools/oslab.py check 9 --impl reference`，编号9仅是此选做扩展的构建编号，不是新增必做实验。工作区为`build/lab02-kernel/IMPL/kernel`，交互磁盘为同层`rootfs.img`，验收使用独立`check-15.img`，结果导出为`result-15.txt`。

## 集成

复制基线到独立工作区，在副本中 `patch -p1` 应用 `IMPL/kernel.patch`，再覆盖 `IMPL/kernel/*` 到其 `kernel/`。分别编译公共 `guest/sem_test.c` 为 `/lab/sem_test`、选定的 `IMPL/guest/pc.c` 为 `/lab/pc`；使用公共来宾编译器，安装为0755。不要编译不同实现的同名程序到同一目录。

来宾验收依次运行：

```sh
/lab/sem_test
/lab/pc 3 500
sync
```

期望 `LAB02-KERNEL PASS` 和 `LAB02-PC PASS`；后者前面501行 `PID: NUMBER`，NUMBER必须恰好为0..500。还应分别测试2和5个消费者。自动化设置超时，挂起不能视为通过。可把输出重定向到 `/var/sem.result`、`/var/pc.result` 后通过公共离线工具导出。不得在QEMU运行时直接操作磁盘。

## 学生任务

1. `sem.c`中完成命名表、参数验证、不泄漏内核地址的句柄、P/V及等待队列。
2. 说明为什么应当原子地完成“检查计数、入队、设为睡眠、切换进程”，为什么简单开关中断不能替换为任意位置的 `sti()`。
3. `pc.c`用文件环形队列和三个内核信号量移植生产者消费者。父进程充当唯一生产者，fork出N个消费者，容量10，默认生产0..500。取数及打印处于同一个互斥区，哨兵用于正常结束所有消费者。
4. 验证无丢失、无重复、顺序正确、子进程状态正常及资源清理。强杀后先重启私有镜像；参考程序仅支持单实例，固定名和`/var/pc.buf`不能供多个实例共享。

## 精确接口与限制

| nr | 接口 | 语义 |
| --- | --- | --- |
| 72 | `sem_open(const char *name, unsigned value)` | 返回正整数句柄；已有同名项忽略value |
| 73 | `sem_wait(int id)` | 0成功；无token则可中断睡眠 |
| 74 | `sem_post(int id)` | 加一个token，唤醒一个睡眠等待者 |
| 75 | `sem_unlink(const char *name)` | 无等待者时删除并使所有旧句柄失效 |

统一错误约定：内核返回负errno，提供的来宾包装器转为`-1`并设置errno。这里主动采用整数句柄，避免原材料中把内核地址当 `sem_t*` 的危险设计；失败不返回NULL。最多16个信号量，名称1..23字节，value范围0..32767。空指针`EFAULT`，空名`EINVAL`，长名`ENAMETOOLONG`，表满`ENOSPC`，无效/过期句柄`EBADF`，计数溢出`ERANGE`，不存在名称`ENOENT`。

等待者存在时unlink返回`EBUSY`，而不是完整POSIX的“解除名字、等最后引用关闭再回收”。无sem_close、权限管理或每进程句柄表。重建同名项会改变代数，旧句柄不能操作新对象；不承诺FIFO公平性。单CPU关闭中断保护表和队列；进入`schedule()`时保持关中断，新任务通过TSS载入自己的EFLAGS。信号打断返回`EINTR`且清除等待队列记录；应用可按需求重试。若已唤醒进程被信号中断，保留token并继续唤醒另一等待者，防止令牌滞留。

本扩展只搭配原版调度器；若与实验三组合，需统一编号并把这里的state赋值改为其日志助手，不能直接串接两个补丁。

## 提交与评分

提交学生补丁及C程序、两种消费者数的完整输出、自检结果、等待队列原子性解释、与POSIX差异。选做扩展按独立100分记录：接口和校验20、原子P/V与阻塞唤醒30、生产消费移植30、测试与报告20。是否折算为课程加分由教师决定；基础实验二按100分评分，不沿用原文80/90分矛盾上限。

## 本次验证范围

在当前Ubuntu/WSL2环境中，学生和参考overlay均已通过patch及内核源码编译，来宾C程序通过公共a.out编译链接。统一构建层已实际启动QEMU验证参考实现，日志见对应`build/lab02-kernel/reference/`；验收输出含上述PASS标志及0退出状态。这些构建产物不作为预置学生答案发布。`manifest.json`记录集成契约，实际入口以根Makefile及`tools/oslab.py`为准。
