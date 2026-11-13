# 实验四：银行家算法——这次资源请求能批准吗？

> 完整仓库包含独立参考实现；学生发布包不含 `reference/`。学生包中跳过参考演示，完成代码后使用默认的 `make check-lab4` 验收自己的实现。

## 目标与准备

完成后，你应能读懂资源矩阵，自己找出一条安全序列，并用 C 实现“先试分配，确认安全后再批准”。需要掌握二维数组、结构体、函数和循环，不需要汇编。

在 Ubuntu 终端、仓库根目录执行；四个算法实验仅需：

```bash
sudo apt update
sudo apt install build-essential python3
make lab4
./build/lab04/student/lab04 labs/lab04/fixtures/classic.txt
```

默认编译 `student/main.c`，初始运行会在标准错误输出 `INCOMPLETE lab04...`，退出码为 3。这表示骨架尚未完成。请修改学生目录；`reference/` 是独立完整参考答案，不被学生程序包含或链接。

不使用根入口也可以构建：

```bash
make -C labs/lab04 IMPL=student BUILD_DIR="$PWD/build/lab04/student"
```

## 先理解，再写程序

把资源看成若干类设备。`maximum[i][j]` 是进程最多需要多少，`allocation[i][j]` 是已经拿到多少，`available[j]` 是系统当前剩余多少。还有：

```text
need[i][j] = maximum[i][j] - allocation[i][j]
```

安全序列是一种“假设按这个顺序让进程得到剩余所需资源并完成，所有进程都能结束”的证明。安全检查中 `work` 初始等于 `available`；模拟某进程完成后，`work += allocation[i]`。不要把模拟完成写回真实分配表，也不要误加 `maximum`。

**手算例子**：只有一类资源，`available=1`。P0 的最大需求为 3、已分配 1；P1 最大需求为 2、已分配 1。P1 还需 1，可以先结束，释放原先分配的 1，`work` 变为 2，随后 P0 也能结束。安全序列为 P1、P0。若先给 P0 再分配 1，则剩余为 0，两者都不能结束，这个请求必须撤销。

“不安全”表示无法保证以后避免死锁，并不表示此刻已经死锁。检查结束的判断必须是**所有进程都已模拟完成**，不能只看最后一次比较是否成功。

## 输入、命令与输出约定

启动格式：`lab04 状态文件`。状态文件按空白分隔，无注释，依次为：

1. 进程数 n、资源种类数 m，均为 1～32。
2. m 个 available 值。
3. n 行 maximum，每行 m 个数。
4. n 行 allocation，每行 m 个数。

资源整数范围 0～1000000，必须有 `allocation <= maximum`。完整示例见 [classic.txt](../labs/lab04/fixtures/classic.txt)。进程编号从 **0** 开始；矩阵行号就是进程编号。程序启动即打印全部矩阵和初始安全性。

标准输入命令以空白分隔，建议每行一条：

| 命令 | 含义 |
|---|---|
| `SHOW` | 输出 AVAILABLE、MAX、ALLOC、NEED |
| `SAFE` | 只检查安全性，输出 `SAFE P...` 或 `UNSAFE` |
| `REQUEST pid r0 ...` | 后面恰好 m 个非负请求量；成功输出 `GRANTED` |
| `QUIT` | 结束；输入 EOF 也结束 |

请求顺序为：检查 pid → 检查不超过 need → 检查不超过 available → 复制整个状态试分配 → 检查安全性。失败输出 `DENIED pid/exceeds_need/unavailable/unsafe_rollback`，保留真实状态并继续读命令。安全检查按 P0 到 P(n-1) 逐轮扫描，因此打印顺序可复现；存在其他安全序列也不算算法错误。

所有请求成功返回退出码 0；只要发生过业务拒绝，最终返回 1。负数、缺参数、非法输入、状态文件错误等返回 2 并停止，以免把后面的命令误当作数据。

## 分步任务

1. 完成输入和维度检查，先实现 `SHOW`，用手算数据验证 `need`。
2. 实现 `safety_check`：局部 `work`、`finish` 和安全序列。若完整一轮无进展，立即判不安全。
3. 实现 `request_resources`：在副本上修改 available 和 allocation；成功才保存副本。也可修改原状态后回滚，但必须证明三个逻辑量全部恢复。
4. 实现命令循环和具体拒绝原因，确保拒绝后仍能继续处理请求。
5. 增加自己的安全、初始不安全、合法但不安全请求、越界和负数数据。

## 运行与预期现象

明确切换参考版本：

```bash
make lab4 IMPL=reference
./build/lab04/reference/lab04 labs/lab04/fixtures/classic.txt < labs/lab04/fixtures/requests.txt
```

预期先输出 `AVAILABLE 3 3 2`。`REQUEST 4 3 3 0` 输出 `DENIED unsafe_rollback`，之后矩阵仍与之前一致；接着 `REQUEST 1 1 0 2` 获得批准，available 变为 `2 3 0`，P1 分配变为 `3 0 2`。该命令文件含有拒绝操作，所以最终退出码为 **1**，不是程序崩溃。

```bash
python3 tests/test_algorithms.py
make lab4 IMPL=student
```

测试脚本默认构建完整参考版本并检查真实行为；它通过不表示你已完成学生版本。完成后，使用下面的学生行为验收和相同输入对照每个输出矩阵。

### 选择验收对象

构建产物按实现隔离：`build/lab04/student/lab04` 与 `build/lab04/reference/lab04`。

```bash
OSLAB_IMPL=reference OSLAB_LAB=4 python3 tests/test_algorithms.py
OSLAB_IMPL=student OSLAB_LAB=4 python3 tests/test_algorithms.py
make check-lab4 IMPL=student
```

`OSLAB_IMPL` 默认 reference；`OSLAB_LAB` 不设则验收四个实验。设置实验号只构建、运行该实验的行为测试。学生骨架尚未完成时，学生行为验收必须失败；不要把默认参考验收通过当作自己的成绩。不设这两个变量时，还额外检查初始学生骨架可编译且明确报告未完成；显式选择实现时不执行该基础设施检查。

## 自检与排错

- 安全检查前后 `SHOW` 完全一致吗？检查函数是不是改了真实 available？
- 拒绝后，不仅 available，而且 allocation 和 need 都恢复了吗？
- 所有进程中只有部分能完成时，是否错误输出 SAFE？
- 数组越界、EOF、负数是否被拦截？若卡住，检查“无进展”退出条件。
- 安全序列不唯一；比较结果时先验证序列有效性，不要只对照字符串。

## 提交与评分（100 分）

提交学生源码、至少四类输入、完整输出、报告。报告包括资源表、手算安全序列、一次批准与一次回滚的前后矩阵、关键函数说明及测试结果。无需打印整份源码，提交带注释的电子文件即可。

| 项目 | 分值 |
|---|---:|
| 输入检查与矩阵展示 | 15 |
| 安全检查与正确终止 | 30 |
| 请求检查、试分配与完整回滚 | 30 |
| 正反例测试和边界数据 | 15 |
| 报告、手算与解释 | 10 |

思考：为什么 `work += allocation` 而不是 `work += maximum`？安全序列是否唯一？若一次拒绝后下一个请求仍失败，如何区分资源确实不足与回滚错误？

本指导保留原 PDF 的矩阵、安全性检查、试分配与回滚目标，修正其中 available 的下标表述和仅凭循环标志判安全的风险，补充输入验证与自动测试。
