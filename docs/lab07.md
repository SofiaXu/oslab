# 实验七：页面置换——满了以后换掉谁？

> 完整仓库包含独立参考实现；学生发布包不含 `reference/`。学生包中跳过参考演示，完成代码后使用默认的 `make check-lab7` 验收自己的实现。

## 目标与准备

用 C 实现 FIFO、LRU、LFU，观察每次访问的物理块状态，区分缺页与置换，保存同一引用序列以公平比较算法。需要数组、结构体和文件读写；不需要真实虚拟内存或汇编。

Ubuntu 依赖：`sudo apt install build-essential python3`。下列命令均在仓库根目录的 Ubuntu 终端执行：

```bash
make lab7
./build/lab07/student/lab07 run fifo 3 labs/lab07/fixtures/sequence1.txt
```

默认学生骨架会输出 `INCOMPLETE lab07...`、退出 3，提示待完成。修改 `labs/lab07/student/`，不链接独立的 `reference/`。

```bash
make -C labs/lab07 IMPL=student BUILD_DIR="$PWD/build/lab07/student"
```

## 三种策略和手算例子

物理块数量固定。访问已经在内存的页叫**命中**；不在内存叫**缺页**，必须调入。若还有空块直接装入；只有没有空块时才会**置换**现有页。

| 算法 | 淘汰依据 | 命中时更新什么 |
|---|---|---|
| FIFO | 最早装入内存的页 | 不改变装入时间 |
| LRU | 最久没有被访问的页 | 最近访问时间 |
| LFU | 本次驻留以来访问次数最少的页 | 驻留访问次数、最近访问时间 |

LFU 同频时淘汰最早装入者。被淘汰后再次装入，从次数 **1** 开始，不继承过去的频率。本套件不定时衰减计数。这是明确的教学约定，避免原材料“一段时间内”“定时清零”却未给周期带来的歧义。

**手算**：2 个物理块，引用 `1 2 1 3`。前三次之后，两页都在内存，1 最近被用过。访问 3 时，FIFO 淘汰最早装入的 1；LRU 淘汰更久没用的 2；LFU 中 1 用了两次、2 一次，也淘汰 2。三种算法本例都是 3 次缺页、1 次置换。

每一步和最终均计算：

```text
缺页率 = 缺页次数 / 已处理引用数
置换率 = 实际淘汰次数 / 已处理引用数
```

程序输出 0～1 的小数，要写成百分数请乘 100。初次填空块算缺页，但不算置换；两个率的分母都不是“缺页次数”。

## CLI 与数据格式

```text
lab07 run fifo|lru|lfu|all 物理块数 序列文件|- [--step] [--save 保存文件]
lab07 generate 种子 引用数量 页号范围 输出文件
```

- 物理块数 1～64，引用数 1～100000，页号为 0～1000000 的整数。
- 序列文件只包含空白分隔的页号，不含页数、注释或连字符。原材料用 `7-0-1` 表达访问次序，实际文件写成 `7 0 1`。
- 文件名 `-` 表示从标准输入读到 EOF。键盘输入完成后按 Ctrl+D；也可使用管道或重定向。
- `all` 使用同一序列分别运行三种算法，每次清空内存和计数。
- `--step` 每次引用前等待标准输入的一行 Enter，随后输出该步结果；若提前 EOF，则报错退出，不会自动把剩余引用跑完。`all --step` 需要三轮 Enter。
- 单步模式必须使用文件输入页号，让标准输入专门接收 Enter；不允许 `- --step`。
- `--save` 将已经读取的完整序列保存，包含原有顺序，不保存算法状态或模拟快照。重新 `run` 即从空内存重放。
- `generate` 的种子为 0～4294967295，数量 1～100000，页号范围 1～1000001；生成的页号位于 `[0,范围)`。

生成器使用 `uint32_t`：每次先更新 `state = 1664525 * state + 1013904223`（按 2³² 取模），再输出 `state % 页号范围`。这保证相同种子与参数跨机器一致，不依赖 C 库 `rand()`。它只用于教学，模运算不保证完美均匀分布。

成功退出 0；参数、数值、文件、提前 EOF 等错误退出 2。所有三种算法的合法数据都应完成，不存在“业务拒绝”退出码 1。

## 分步任务

1. 读入序列并检查范围，使用 occupied 标志或 -1 表示空块，页号 0 必须合法。
2. 实现命中查找，先把 FIFO 跑通，记录装入时间。块按下标稳定显示，不因显示而排序。
3. 加入 LRU 的最近访问时间和 LFU 的驻留计数，单独测试同频规则与重装计数。
4. 每一步输出访问页、命中或缺页、受害页、全部块、累计计数与两个率。
5. 实现 `all`、`--save`、生成与重放，最后实现 Enter 单步。
6. 用原题两组序列分别比较 3、4、5 个物理块，共 18 组结果。再保存一组生成序列用于重复实验。

输出中 `victim=-1` 表示没有实际淘汰，`frames=7,0,-1` 表示第三个块为空。命中不会改变物理块编号。`STEP` 是每一步轨迹，`SUMMARY` 是汇总。

## 运行与预期

```bash
make lab7 IMPL=reference
./build/lab07/reference/lab07 run all 3 labs/lab07/fixtures/sequence1.txt
./build/lab07/reference/lab07 run lru 4 labs/lab07/fixtures/sequence2.txt --step
printf '1 2 1 3\n' | ./build/lab07/reference/lab07 run all 2 -
./build/lab07/reference/lab07 generate 42 30 10 build/pages.txt
./build/lab07/reference/lab07 run all 3 build/pages.txt --save build/pages-copy.txt
cmp build/pages.txt build/pages-copy.txt
```

原题第一组（20 次引用，3 块）的汇总应为：

| 算法 | 缺页 | 置换 | 缺页率 | 置换率 |
|---|---:|---:|---:|---:|
| FIFO | 15 | 12 | 0.750000 | 0.600000 |
| LRU | 12 | 9 | 0.600000 | 0.450000 |
| LFU | 13 | 10 | 0.650000 | 0.500000 |

原题第二组完整 24 次引用保存在 [sequence2.txt](../labs/lab07/fixtures/sequence2.txt)。第一组在 [sequence1.txt](../labs/lab07/fixtures/sequence1.txt)，另有 [lfu-tie.txt](../labs/lab07/fixtures/lfu-tie.txt) 检查同频及重装。

```bash
for frames in 3 4 5; do
  ./build/lab07/reference/lab07 run all "$frames" labs/lab07/fixtures/sequence1.txt
  ./build/lab07/reference/lab07 run all "$frames" labs/lab07/fixtures/sequence2.txt
done
python3 tests/test_algorithms.py
make lab7 IMPL=student
```

脚本默认构建参考版本，逐步对比独立模型并检查生成重放；用下方学生行为验收让同一批测试检查学生版本。

### 选择验收对象

构建产物按实现隔离：`build/lab07/student/lab07` 与 `build/lab07/reference/lab07`。

```bash
OSLAB_IMPL=reference OSLAB_LAB=7 python3 tests/test_algorithms.py
OSLAB_IMPL=student OSLAB_LAB=7 python3 tests/test_algorithms.py
make check-lab7 IMPL=student
```

`OSLAB_IMPL` 默认 reference；`OSLAB_LAB` 不设则验收四个实验。设置实验号只构建、运行该实验的行为测试。学生骨架尚未完成时，学生行为验收必须失败；不要把默认参考验收通过当作自己的成绩。不设这两个变量时，还额外检查初始学生骨架可编译且明确报告未完成；显式选择实现时不执行该基础设施检查。

## 自检与排错

- `replacements <= faults <= references`，有空块时不能增加 replacements。
- 若只访问同一页 20 次，只有第一次缺页，后面全部命中。
- 页被重新装入后频率是否归 1？平频是否按装入时间而非最近使用时间？
- FIFO 命中时改变队列会偷偷变成另一种算法；LRU 忘记更新命中时间也会出错。
- 每次运行 `all` 的下一个算法是否重置了帧和计数？
- 错误输入应明确报错；除法应转换为浮点数，避免整数除法得到 0。

## 提交与评分（100 分）

提交学生源码、18 组原题结果、固定种子序列及重放结果、报告。报告手画至少 6 次引用的帧表，说明缺页与置换的区别，对比三种算法并解释一处不同的受害页选择。

| 项目 | 分值 |
|---|---:|
| FIFO/LRU/LFU 各算法正确性 | 45 |
| 命中、缺页、置换与率的展示 | 15 |
| 输入检查、文件读写、生成与重放 | 15 |
| 单步、边界测试与结果可重复性 | 15 |
| 报告、手算与分析 | 10 |

思考：为什么缺页次数常大于置换次数？物理块增加是否一定让 FIFO 缺页减少？哪种访问模式会让“历史上热门但现在不再使用”的页面影响 LFU？

本实验保留原材料两组序列、三种算法、3/4/5 块、动态序列保存与重放；用终端 Enter 代替 Windows WM_TIMER，修正旧示例中不完整的 C++ 菜单与不明确的 LFU 周期。
