# 实验五：用内核栈完成进程切换

> 完整仓库包含独立参考实现；学生发布包不含 `reference/`。学生包中跳过参考演示，完成代码后使用默认的 `make check-lab5` 验收自己的实现。

你将把 Linux 0.11 的“CPU 按 TSS 自动切换进程”改成“软件保存旧栈指针、装入新栈指针”。调度算法保持原样。最终成果必须在真正的 Linux 0.11 内核中启动、fork、运行多个进程和 wait；终端上的算法模拟不算完成。

本实验独立使用干净基线，不要求先完成实验一或三。建议先读[环境准备指导](setup-wsl2.md)，掌握 C 指针、结构体、函数调用以及 fork 的父子返回值。你不需要从零熟练编写汇编：**本实验要求使用 AI 生成软件切换汇编，再自行解释、集成和调试。** 提供独立参考实现用于核对。

## 1. 从哪里开始

在仓库根目录的 **Ubuntu 终端** 中执行：

```bash
make doctor
make prepare
make lab5
make run-lab5
```

默认使用学生版本。它保留旧的硬件切换，目的是让你有一个能编译和启动的起点。**学生骨架能启动，或者它的 fork 测试通过，都不代表完成本实验。** 骨架包含 `TODO_LAB5_SOFTWARE_SWITCH`，验收会拒绝仍有该标记的实现；还需要检查实际切换指令，不能只删标记。

完成后运行：

```bash
make check-lab5
python3 tests/test_stack_layout.py -v
```

第二条命令验证仓库提供的帧布局、参考实现和原始骨架，不替代你的学生版本的来宾验收。参考路径可以单独运行：

```bash
make IMPL=reference lab5
make IMPL=reference run-lab5
make IMPL=reference check-lab5
```

两个版本的内核工作区分别是：

- `build/lab05/student/kernel/`
- `build/lab05/reference/kernel/`

学生应修改 `labs/lab05/student/kernel/` 中的源文件，再通过套件重新构建。不要只修改 `build/` 中的副本，否则重新准备工作区后会丢失。不要修改 `vendor/linux-0.11/` 或其他实验目录。

## 2. 先把三个概念分开

**调度**决定“下一个进程是谁”。`kernel/sched.c` 的 `schedule()` 已经算出 `next`，这部分不需要重写。

**上下文切换**让 CPU 从旧进程的执行现场继续到新进程的执行现场。本实验改写这里。普通 C 函数调用只能顺着同一条调用链返回；切换栈以后，同一条 `ret` 可以返回到另一条调用链。

**用户态返回**是从内核回到用户程序，由 `iret` 完成。新 fork 的孩子从未调用过 `schedule()`，所以必须人为构造一份“像是已经保存过”的内核栈，让它第一次切换上来时能返回到用户态。

每个普通进程占有一页 PCB＋内核栈：

```text
低地址 p ┌──────────────────────┐
         │ struct task_struct   │  PCB：状态、资源、LDT、浮点保存区等
         ├──────────────────────┤
         │ 可用内核栈空间        │
         │          ↓ 栈向低地址增长
p+4096   └──────────────────────┘  下一次用户态进内核时的栈顶
```

`kernel_esp` 放在 `task_struct` **最后面**。`system_call.s` 已经写死了 `state`、`counter`、`signal`、`blocked` 的偏移，插到结构体中间会破坏它们。结构体变大后，可用内核栈略微减少，仍须在同一页内。

## 3. 为什么仍然需要一个 TSS

原版 `switch_to` 用 `ljmp` 跳到另一个 TSS 描述符，让 CPU 自动保存和装载现场。本实验的参考路径不再执行这种硬件任务切换。

但用户态发生中断或系统调用时，CPU 仍要知道该用哪个内核栈。这里保留启动进程的 TSS：

1. `sched_init()` 只执行一次 `ltr(0)`，TR 指向 `_TSS(0)`。
2. `lab5_bootstrap_tss` 始终指向这个 TSS。
3. 每次真正切换时，令它的 `esp0 = (unsigned long)next + PAGE_SIZE`。
4. 执行 `lldt` 装入下一进程的 LDT，再恢复段寄存器。

参考路径不会为每次调度执行 `ltr`，也不会远跳到各进程的 TSS。为兼容学生硬件骨架，补丁暂时保留子进程的 TSS 描述符和旧 TSS 字段；参考路径只使用其中的浮点保存区等数据。存在这些结构体不等于仍在使用硬件切换。

共享 TSS 的 `ss0` 保持内核数据段选择子 `0x10`：CPU 进入 ring 0 时用 ss0:esp0 作为栈，不是拿用户的 SS/ESP 当内核栈。

Linux 0.11 的进程共享同一组页目录，使用 LDT 区分用户地址基址；本实验不引入每进程 CR3 切换，也不改为现代 Linux 的调度实现。

## 4. 汇编接口和必须满足的约定

接口在补丁后的 `include/linux/sched.h` 中声明：

```c
void lab5_switch(struct task_struct *next, unsigned long ldt_selector);
```

它使用 i386 cdecl 调用约定：调用者压入参数，`call` 压入返回地址；EAX/ECX/EDX 可以被函数破坏，EBX/ESI/EDI/EBP 必须恢复。段寄存器和进入函数时的 EFLAGS 也属于要保留的现场。

实现文件是 `kernel/lab5_switch.S`，大写 `.S` 表示先经过 C 预处理。它包含自动生成的 `lab5_offsets.inc`。这个文件由 `lab5_offsets.c` 使用目标编译器的 `__builtin_offsetof` 生成，不要手算并写死 PCB 中 `kernel_esp` 的偏移。

软件切换保存帧的布局由 `kernel/lab5.h` 定义：

```text
保存的 ESP -> + 0  GS           每格都是 4 字节
              + 4  FS
              + 8  ES
              +12  DS
              +16  EDI
              +20  ESI
              +24  EBX
              +28  EBP
              +32  EFLAGS
              +36  返回地址     正常进程：回到 schedule() 的调用点
              +40  参数 next
              +44  参数 ldt_selector
```

正常切换顺序：先 `pushfl` 保存原 IF，再 `cli`；保存寄存器和段选择子；若 next 等于 current，直接恢复；否则保存旧 `kernel_esp`，更新 current、共享 TSS.esp0、LDT 和 TS，再装入新 `kernel_esp`，恢复现场并 `ret`。

有四个容易遗漏的约束：

- 从更新 current 到装入并恢复新栈期间必须关中断。返回时用 `popfl` 恢复各自原有 IF，不能无条件 `sti`。有些内核调用者本来就在关中断区。
- 必须在 `lldt` **之后**恢复 FS/GS。选择子即使数值相同，隐藏的段描述符缓存也可能仍指向旧进程的数据。
- FS 不总是 `0x17`。内核文件操作可能暂时把 FS 设为 `0x10`，正常切换需要原样保存、恢复。新孩子的内核执行约定可以用 FS=`0x17`，用户 FS 则从用户返回帧恢复。
- DS/ES 在本函数入口是内核段 `0x10`；所有 PCB 和全局变量访问必须遵守这一约定。装入新 ESP 后不能再访问旧栈上的参数。

## 5. fork 的孩子应该“返回”到哪里

`kernel/system_call.s` 的 `sys_fork` 把父进程现场传给 `copy_process()`。补丁在孩子变成 `TASK_RUNNING` **之前**调用：

```c
lab5_init_stack(p, ebp, edi, esi, gs, ebx, ecx, edx,
                fs, es, ds, eip, cs, eflags, esp, ss);
```

你需要在学生版 `kernel/lab5.c` 中实现这个函数。这是 C 集成任务，空函数只是旧硬件骨架的占位。可以让 AI 协助，但必须自己核对字段和偏移。

孩子的完整初始内核栈占 88 字节，放在 PCB 页顶端：

```text
p->kernel_esp -> + 0  GS = 父进程的用户 GS
                 + 4  FS = 0x17       ┐
                 + 8  ES = 0x10       │ 供软件切换函数恢复
                 +12  DS = 0x10       │
                 +16  EDI = 用户 EDI  │
                 +20  ESI = 用户 ESI  │
                 +24  EBX = 用户 EBX  │
                 +28  EBP = 用户 EBP  │
                 +32  EFLAGS = 2      │ 内核 IF=0，直至最后 iret
                 +36  lab5_fork_return┘ ret 消耗此地址
                 +40  EAX = 0         ┐ fork 在孩子中返回 0
                 +44  EBX             │
                 +48  ECX             │
                 +52  EDX             │ ret_from_sys_call 的输入
                 +56  用户 FS         │
                 +60  用户 ES         │
                 +64  用户 DS         │
                 +68  用户 EIP        │
                 +72  用户 CS         │
                 +76  用户 EFLAGS     │
                 +80  用户 ESP        │
                 +84  用户 SS         ┘
p + PAGE_SIZE -> +88
```

孩子第一次切换上来，恢复前 36 字节后，`ret` 跳到 `lab5_fork_return`；这时 ESP 正好指向 `EAX=0`。该入口直接 `jmp ret_from_sys_call`，后者走正常信号检查、弹出用户现场，最后 `iret`。

为什么不能直接 `ret` 到用户 EIP？用户态返回还需要 CS、EFLAGS、ESP、SS。为什么还要单独保留 EDI/ESI/EBP？原来的 `ret_from_sys_call` 根本不恢复这三个寄存器；它假定 C 代码遵守调用约定。新孩子没有走过普通调用链，必须自己准备。

`lab5.h` 的两个帧结构体是上述图的 C 表达。建议先把每个字段填上，再设置 `p->kernel_esp`，并检查结构体与帧没有重叠。

## 6. 浮点现场：不能忘记 TS

即使你的 C 程序只写整数，其他进程也可能使用 x87 浮点单元。原来 CPU 做硬件任务切换时会自动设置 CR0.TS，软件切换必须自己补上：

- 真正换到另一个任务后，先置 TS。
- 如果新任务就是 `last_task_used_math`，它的浮点现场仍在硬件里，可以 `clts`。
- 否则保持 TS，下次 x87 指令触发 `device_not_available`，原有 `math_state_restore()` 会保存旧拥有者、恢复新拥有者。
- 同一进程的空切换不必改变 TS。

fork 还有一个特殊问题：`fnsave` 把浮点现场存入孩子的 `tss.i387` 后，会重置硬件浮点单元。若仍把父进程视为现场拥有者，却不恢复硬件，父进程继续计算就会出错。因此公共补丁在 `fnsave` 后立即 `frstor` 同一份快照，既给孩子初始状态，也保留父进程状态。

## 7. 必做：用 AI 生成、检查和调试汇编

先保存自己的初稿栈图，再向 AI 提交下面的提示词。允许多轮修改；提交原始提示词、AI 生成代码和你实际采用的修改记录。**直接复制参考答案或只让 AI 解释已有参考代码，不能替代生成与调试任务。**

```text
请为教学 Linux 0.11 编写 i386 AT&T/GAS 软件内核栈切换汇编。
目标：GCC -m32 -std=gnu89，无优化、无 PIE、无 SSE/MMX，cdecl，4 字节栈对齐。
文件：kernel/lab5_switch.S，入口 lab5_switch(next, ldt_selector)。
接口声明和帧结构在 kernel/lab5.h、include/linux/sched.h。
需要导出 lab5_switch 和 lab5_fork_return，后者 jmp ret_from_sys_call。
全局变量：current、last_task_used_math、lab5_bootstrap_tss。
包含 lab5_offsets.inc，使用 LAB5_KERNEL_ESP、LAB5_TSS_ESP0、
LAB5_PAGE_SIZE 和 LAB5_NEXT（switch_frame.eip 的偏移）。
不要自己猜 PCB 偏移。

保存帧从低到高：gs fs es ds edi esi ebx ebp eflags 返回地址。
调用入口 DS/ES 是 0x10，FS/GS 需要保存，不允许假定 FS 恒为 0x17。
先保存 EFLAGS，再关中断；切换完成恢复原 IF，不得无条件 sti。
同任务直接恢复返回。不同任务保存旧 ESP，更新 current 和共享 TSS.esp0。
TR 始终是启动 TSS，不允许 ljmp/lcall TSS 或切换 TR。
装入新 LDT 必须在恢复 FS/GS 前。CR3 共享，不用切换。
软件补足硬件任务切换的 TS 行为：换任务先置 TS；若 next 是
last_task_used_math，则 clts，否则由原有 #NM 处理器延迟恢复 x87。
装入新 ESP 后不能再读旧参数。

请逐条注释，并画出普通返回与 fork 首次返回时的栈图。
同时给出 lab5_init_stack 的 C89 实现建议：在 PCB 页顶放置软件保存帧
和 ret_from_sys_call 的 12 字用户帧，孩子 EAX=0，保留 EDI/ESI/EBP/GS。
请解释为什么设置子进程的内核 EFLAGS=2、用户 EFLAGS 保留原值。
下面附上实际 lab5.h、lab5_offsets.c 和 system_call.s 内容：
[粘贴这些文件，不要只粘贴文件名]
```

完成两部分修改：

1. 用审查后的 AI 软件切换代码替换学生 `lab5_switch.S` 的硬件后备实现。检查引用符号、参数偏移、段恢复顺序、IF、TS，以及同任务分支。
2. 实现学生 `lab5.c` 的 `lab5_init_stack`，核对补丁中的调用时机；编译运行，定位至少一个实际问题或解释你如何证实高风险路径正确。确实完成后再移除对应 TODO 标记。

在报告中用自己的话解释 `movl %esp,...`、`movl ...,%esp`、`lldt`、`popfl` 和最后的 `ret`。不要把“AI 说正确”当成证据。

## 8. 运行与验收

来宾测试源码在 `labs/lab05/guest_test.c`。宿主机用套件运行库构建，不链接 Ubuntu glibc：

```bash
python3 tools/guest_build.py labs/lab05/guest_test.c build/lab05/student/guest/lab05_test
```

套件负责把程序放入该实验磁盘。若手动部署，用套件的 Minix 文件交换工具写入 `/lab/lab05_test`，不要对正在运行的磁盘写入文件。进入 **Linux 0.11 来宾 shell** 后：

```sh
/lab/lab05_test
cat /var/lab05.result
/lab/lab05_test 12 120000
ls /
```

默认四轮，每轮创建四个孩子，父进程与孩子同时运行。第二次是加长压力测试。程序先写 `LAB05_RUNNING` 清除旧 PASS，最终写 `LAB05_PASS` 或 `LAB05_FAIL`，stdout 和结果文件都有标记；如果 `/var` 不存在或文件写入失败，以本次运行的 stdout、退出状态与完整执行过程为准，不能读取旧文件判断成功。

它核对：

- fork 刚返回、尚未进入普通 C 代码前，EBX/ECX/EDX/EDI/ESI/EBP 仍然正确，父子 x87 栈中的值都保留。
- 多进程 CPU 运行与大量 getpid 系统调用期间，进程各自的六个寄存器标记、x87 值及舍入模式不串扰，用户段和 IF/DF 正确。
- 孩子正常退出，父进程 wait 回收，反复创建后不耗尽进程槽。

探针错误码：1=整数寄存器，2=x87 数值，3=x87 控制字，4=用户段选择子，5=用户 EFLAGS；fork 探针的 -99 表示首次返回寄存器错误，-98 表示首次返回浮点值错误。正常 fork 的资源不足也会报告负数，结合日志区分。

最终还要确认 shell 能执行普通命令，且切换对象中没有 `ljmp/lcall`：

```bash
objdump -dr build/lab05/student/kernel/kernel/lab5_switch.o
python3 tests/test_stack_layout.py --check-switch build/lab05/student/kernel/kernel/lab5_switch.o
```

对象检查会拒绝硬件远跳转/重载 TR，并核对软件 ESP、LDT、TS 操作。它属于结构检查，不是语义正确性的证明。

验收不能只看 PASS 字样：硬件骨架也可能通过来宾测试，必须结合学生源代码、未完成标记、反汇编、AI 记录和运行证据判断。默认负载是回归测试，不证明每条分支都被动态覆盖；同任务返回、调用前 IF=0、FS 临时为 0x10 等路径还需单步检查或定向实验。

## 9. 调试时先看什么

| 现象 | 优先检查 |
|---|---|
| 编译成功，第一次 fork 就挂起或重启 | 孩子 ESP 是否指向 GS；返回地址是否为 lab5_fork_return；用户帧有无错一格 |
| 孩子返回值不为 0 | 用户帧 EAX；是不是直接跳进了 syscall 返回路径而漏掉一层帧 |
| C 局部变量或循环突然损坏 | EDI/ESI/EBP 保存顺序和子进程初值；4 字节对齐编译选项 |
| 多进程读写彼此数据或出现段错误 | lldt 是否在恢复 FS/GS 前；有没有错误地把 FS 固定为 0x17 |
| 从用户态下一次进入内核就崩溃 | 启动 TSS 的 esp0 是否更新为 next+4096；TR 是否仍是启动 TSS |
| 浮点测试失败，整数测试正常 | 是否置 TS、拥有者判定是否正确、fork 的 fnsave 后是否 frstor |
| 运行一段时间后不再调度 | 是否错误关闭了返回任务的 IF，或意外允许切换临界区中断 |

需要单步时，使用构建出来的 `tools/system` 作为 GDB 符号文件。先用 `make debug-lab5` 启动暂停的 QEMU（GDB 端口仅绑定本机），再开一个 Ubuntu 终端执行：

```text
gdb build/lab05/student/kernel/tools/system
(gdb) target remote :1234
(gdb) break lab5_switch
(gdb) break lab5_fork_return
(gdb) continue
(gdb) p/x current
(gdb) p/x lab5_bootstrap_tss->esp0
(gdb) p sizeof(struct task_struct)
(gdb) x/10i $eip
```

在旧任务已经保存 `kernel_esp` 后，才使用 `x/22wx current->kernel_esp` 查看帧；初始 task 0 在第一次保存前该字段为零。用 `stepi` 看 ESP 切换点，并记录 next 与共享 TSS 栈顶的关系。QEMU monitor 的 `info registers` 可以辅助查看 TR/LDT；不要假设所有 GDB 远程目标都支持单独读取 TR。

## 10. 提交与评分（100 分）

| 项目 | 分值 | 证据 |
|---|---:|---|
| 栈图和接口理解 | 20 | 普通切换帧、孩子双层帧、五条关键指令解释 |
| AI 生成与审查 | 20 | 原提示词、原输出、修改记录、针对 IF/FS/TS 的审查 |
| 软件切换和 C 集成 | 30 | 学生源码、编译产物、无硬件任务切换的反汇编 |
| 真实内核运行与调试 | 20 | 本次启动、默认与加长测试、wait 与 shell 证据、调试记录 |
| 报告与思考 | 10 | 结果分析、边界说明、下述问题的独立回答 |

保留原实验以“内核栈切换替代 TSS 硬件切换”为中心的目标，把汇编学习改成可审查的 AI 生成实践；按本表统一为 100 分。报告使用套件的 [Markdown 模板](report-template.md)，附学生修改过的源文件，不提交整个 `build/` 或磁盘镜像。

思考题：为什么只有一个共享 TSS 仍能从用户态进入正确的内核栈？为什么 next==current 也不能无条件开中断？如果删除 FS 的重新装载，选择子仍是 0x17，为什么可能出错？fork 的孩子为什么需要一个根本没有执行过的返回地址？怎样设计一个能暴露错误 TS 管理的实验？软件切换相较硬件切换获得了什么控制权，又多承担了哪些责任？

### 原材料中的三个问题

为方便与原实验对照，保留下面的代码片段（按 GAS 语法补全空格）。原材料的手工压栈布局与本套件的结构体帧不同，回答时先标明自己讨论的布局。

```asm
movl tss, %ecx
addl $4096, %ebx
movl %ebx, ESP0(%ecx)
```

为什么要加 4096？为什么这里没有同时设置 TSS 中的 SS0？本套件中对应的共享 TSS 和栈顶从哪里得到？

```c
*(--krnstack) = ebp;
*(--krnstack) = ecx;
*(--krnstack) = ebx;
*(--krnstack) = 0;
```

孩子第一次返回时 EAX 应是多少，由哪段工作保证？EBX、ECX 和 EBP 来自哪里，分别为何要进入孩子的内核帧？如果不保存 EBP，哪些代码可能仍看似正确，哪些会失败？在本套件双层帧中找出对应字段。

最后解释：为什么切换 LDT 后要重新装载 FS 的描述符缓存？若提前装载会怎样？为什么本套件除了常见的用户数据选择子 `0x17`，还要保存可能临时指向内核数据的 `0x10`？

## 维护者：补丁和编译约定

`labs/lab05/kernel.patch` 是独立的统一补丁，对干净移植基线使用 `-p1`。它不包含 GCC 兼容改造，不依赖实验一或三。正常教学只需前文的 `make lab5`、`make run-lab5` 和 `make check-lab5`，主工具自动完成工作区、补丁和 overlay。以下命令仅供维护者核对集成：主工具先创建各自工作区，再依次应用补丁和对应 overlay：

```bash
patch --batch -p1 -d build/lab05/reference/kernel < labs/lab05/kernel.patch
cp -a labs/lab05/reference/kernel/. build/lab05/reference/kernel/kernel/
```

学生版本把上述所有 `reference` 都替换为 `student`。不要对已经打过补丁的目录重复执行。构建副本必须清除继承的 `.o`、`tools/system` 和 `Image` 等旧产物，确保新子目录构建规则真正运行；套件的准备与构建流程负责这一步。

构建依赖 apt 提供的 `build-essential`、`binutils`、`patch`、`python3`，运行使用套件 QEMU 依赖。内核必须使用主基线的 `-m32 -march=i386 -std=gnu89 -fno-pie -fno-pic -mno-sse -mno-mmx -msoft-float -mpreferred-stack-boundary=2 -mincoming-stack-boundary=2` 等既有选项，不优化；补丁不修改 `Makefile.header`。Make 会用 `$(CC) $(CFLAGS) -S` 生成偏移，再预处理、汇编 `.S`，无需 nasm 或旧 GCC。

`python3 tests/test_stack_layout.py -v` 在临时目录应用补丁，验证学生与参考内核对象链接、i386 帧构造和参考反汇编。它不会修改 vendor 或正式实验工作区，也不会声称已通过真实启动。学生发布包没有参考实现时，此组参考回归测试会明确跳过；`--check-switch` 入口和 `make check-lab5` 仍可用于真实学生实现。主集成测试还应启动参考内核，部署并执行 guest_test、导出最终标记、加长测试并确认 shell 存活；学生验收必须拒绝保留 `TODO_LAB5_SOFTWARE_SWITCH` 的源码，不能因硬件后备路径产生 PASS 而放行。
