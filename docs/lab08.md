# 实验八：模拟文件系统——同名文件为什么不会冲突？

> 完整仓库包含独立参考实现；学生发布包不含 `reference/`。学生包中跳过参考演示，完成代码后使用默认的 `make check-lab8` 验收自己的实现。

## 目标与准备

用 C 在内存中建立二级目录，实现文件创建、删除、打开、关闭与权限检查。理解 MFD、UFD 和打开表的不同作用，练习字符串、结构体、数组和命令解析。不需要编写真实磁盘文件系统。

Ubuntu 安装 `sudo apt install build-essential python3` 后，在仓库根目录运行：

```bash
make lab8
./build/lab08/student/lab08
```

默认学生骨架输出 `INCOMPLETE lab08...`，退出码 3。请修改 `labs/lab08/student/`；完整参考在独立的 `reference/`。

```bash
make -C labs/lab08 IMPL=student BUILD_DIR="$PWD/build/lab08/student"
```

## 二级目录和手算

MFD（主文件目录）保存用户到 UFD 的对应关系；每个 UFD（用户文件目录）保存该用户的文件名、权限和内容。查找 `notes` 时，先定位当前用户，再在其 UFD 中按名查找。`alice/notes` 和 `bob/notes` 是两个不同文件。

“文件存在”不等于“已打开”。创建只登记文件、内容为空；OPEN 才进入打开表；CLOSE 释放打开名额，但不删除文件。本实验可在每个文件内保存 opened 标志来表示打开表，用户另有 open_count。删除已打开文件必须拒绝。

**手算**：K=1，Alice 创建 a、b。打开 a 后打开 b 被拒绝；关闭 a 后才可打开 b。切到 Bob 后，他自己的打开数仍从 0 开始；再切回 Alice，b 仍处于打开状态。模拟用户身份用于理解目录隔离，不是实际登录或安全认证。

权限用 `r`（读）、`w`（写）、`x`（模拟执行）表示。例如 `r` 可以读但不能写，`x` 只能模拟执行。OPEN 本身不授予权限；READ/WRITE/EXEC 每次检查文件权限。DELETE 属于当前用户的目录管理，本实验不依据文件读写位限制删除，但要求先关闭。

## 完整命令约定

启动：`lab08 [K]`。K 为每个用户最多同时打开的文件数，默认 2，范围 1～32。最多 16 个用户，每用户最多 32 个文件。每次运行重新开始，退出丢弃全部状态，不挂载真实文件系统、不访问宿主用户文件。

命令每行一条、区分大小写；空行忽略。名字为 1～31 字节的英文字母、数字、下划线或连字符，不支持路径或空格。

| 命令 | 操作与结果 |
|---|---|
| `USER alice` | 创建用户及空 UFD，不自动登录 |
| `LOGIN alice` | 切到已存在的用户；不需要密码 |
| `CREATE notes rw` | 创建空文件，权限可组合 `r/w/x`，每位不能重复；`-` 表示无权限 |
| `DELETE notes` | 删除当前用户的已关闭文件 |
| `OPEN notes` | 打开当前用户的文件；重复打开或达到 K 均拒绝 |
| `CLOSE notes` | 关闭已经打开的文件 |
| `READ notes` | 要求已打开且有 r；输出 `DATA 内容` |
| `WRITE notes hello` | 要求已打开且有 w；完整覆盖内容，不追加 |
| `EXEC app` | 要求已打开且有 x；只输出 `EXEC_SIMULATED 用户/文件` |
| `LIST` | 显示 MFD 与各 UFD 的元数据、权限、长度和打开数 |
| `QUIT` | 结束；EOF 也可结束 |

WRITE 内容是**一个不含空白的非空字符串**，最多 1024 字节；引号没有特殊意义，不支持多词或清空命令。每条命令行应短于 2047 字节。`LIST` 是教学观察入口，允许查看其他用户的元数据，但读取内容仍必须通过当前用户的 READ；没有跨用户路径参数。

每个用户独立计算 K，切换用户保留原来的打开表。程序不模拟多进程共享描述符、共享文件、密码、目录权限、磁盘块或持久化。`EXEC` 不调用宿主 shell 或任何真实程序，即使文件内容看起来像命令也只当普通字符串。

成功操作输出 `OK ...`；失败输出具体的 `DENIED 原因`，保持状态不变并继续处理后续命令。最终全成功退出 0；发生过命令拒绝则退出 1；启动参数、读取失败或过长输入行等致命错误退出 2。

## 分步任务

1. 建立 MFD、UFD 和文件结构；初始化当前用户为 -1，空文件内容为 `""`。
2. 实现 USER、LOGIN、CREATE、LIST，用相同文件名验证用户隔离。
3. 实现 OPEN/CLOSE 与打开数；检查不存在、重复打开、重复关闭、达到 K 等情况。
4. 实现 DELETE：先校验，再清空目录项，确保重复创建可复用空位置。
5. 实现 READ/WRITE/EXEC，先检查已打开，再检查权限；权限不足不能改变内容。
6. 实现逐行参数检查和错误恢复。不要用 `==` 比较 C 字符串，使用 `strcmp`；不要把输入缓冲区地址永久存进目录项，应复制字符串。

## 运行与预期

```bash
make lab8 IMPL=reference
./build/lab08/reference/lab08 < labs/lab08/fixtures/session.txt
./build/lab08/reference/lab08 2 < labs/lab08/fixtures/denied.txt
```

正常会话应输出 `DATA hello` 和 `EXEC_SIMULATED alice/app`。Alice 删除自己的 notes 后，Bob 仍可创建并读自己的 notes，初始内容为空，故输出 `DATA `。Alice 的 app 和 Bob 的 notes 各占用自己用户的一个打开名额。

拒绝会话应出现以下原因：

- `permission`：给只读文件 WRITE；文件内容仍为空。
- `file_open`：删除未关闭文件。
- `open_limit`：K=2，试图同时打开第三个文件。
- `no_such_file`：Bob 无法打开 Alice 的 secret。

拒绝会话最终退出码为 1，这是预期业务结果。手动体验 K=1：

```bash
./build/lab08/reference/lab08 1
```

依次输入 `USER alice`、`LOGIN alice`、`CREATE a rw`、`CREATE b r`、`OPEN a`、`OPEN b`，观察拒绝；再 `CLOSE a`、`OPEN b`、`LIST`、`QUIT`。

```bash
python3 tests/test_algorithms.py
make lab8 IMPL=student
```

自动测试默认构建参考程序，验证容量、权限和错误后的状态；用下方学生行为验收可让同一套测试验证你的代码。

### 选择验收对象

构建产物按实现隔离：`build/lab08/student/lab08` 与 `build/lab08/reference/lab08`。

```bash
OSLAB_IMPL=reference OSLAB_LAB=8 python3 tests/test_algorithms.py
OSLAB_IMPL=student OSLAB_LAB=8 python3 tests/test_algorithms.py
make check-lab8 IMPL=student
```

`OSLAB_IMPL` 默认 reference；`OSLAB_LAB` 不设则验收四个实验。设置实验号只构建、运行该实验的行为测试。学生骨架尚未完成时，学生行为验收必须失败；不要把默认参考验收通过当作自己的成绩。不设这两个变量时，还额外检查初始学生骨架可编译且明确报告未完成；显式选择实现时不执行该基础设施检查。

## 自检与排错

- 对每个用户，open_count 是否等于其 opened 文件数，且不大于 K？关闭后是否恢复名额？
- 登录失败是否保持原用户？重名用户、重名文件、非法名字是否先检查再改状态？
- 两个用户的同名文件写入不同内容，切换后是否各读到自己的内容？
- READ/WRITE/EXEC 是否都检查打开状态和对应权限？仅有 x 的文件能否拒绝 READ？
- 拒绝删除或写入后 LIST 是否保持原长度、权限和打开状态？
- 第 33 个文件、第 17 个用户、1025 字节内容是否明确拒绝而非数组越界？

## 提交与评分（100 分）

提交学生源码、正常与拒绝命令文件、输出、报告。报告画出两个用户及同名文件的 MFD/UFD 图，说明打开表如何表示，列出权限与错误操作测试，解释为什么 EXEC 不能调用宿主系统。

| 项目 | 分值 |
|---|---:|
| MFD/UFD、多文件与用户隔离 | 25 |
| CREATE/DELETE/OPEN/CLOSE 和 K 限制 | 25 |
| READ/WRITE/EXEC 权限和安全模拟 | 20 |
| 输入、容量、拒绝后状态及测试 | 20 |
| 报告、目录图与解释 | 10 |

思考：为什么创建和打开不能合并为同一概念？为什么 K=1 不等于“只能保存一个文件”？若允许多个进程同时打开同一个文件，还需要哪些额外数据？

本指导保留原材料二级目录、四个核心命令和保护措施，将“每用户最多一个文件”扩展为多个文件，使 K 有实际意义；增加读写和模拟执行以验证权限，替换原示例中不完整的数据类型、指针和字符串比较代码。
