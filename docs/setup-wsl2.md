# 在 Windows 上准备实验环境

目标环境是 **WSL2 中的 Ubuntu 24.04，CPU 架构 x86_64（Ubuntu 称 amd64）**，QEMU 图形窗口由 WSLg 显示。建议使用 Windows 11；Windows 10 的 WSLg 需要 Build 19044 或更新。Windows 安装步骤以 [Microsoft WSL 文档](https://learn.microsoft.com/en-us/windows/wsl/install)为依据，图形支持与更新步骤见 [WSLg 文档](https://learn.microsoft.com/en-us/windows/wsl/tutorials/gui-apps)。ARM Windows 不属于本套件默认环境，不要把 ARM Ubuntu 当成 x86_64 环境。

## 1. 在 Windows 安装 WSL2

以下代码块在 **管理员 PowerShell** 执行。先保存其他 WSL 任务。

```powershell
wsl --list --online
wsl --install -d Ubuntu-24.04
```

首次安装若提示重启，重启 Windows 后继续。首次打开 Ubuntu 时创建 Linux 用户名和密码；密码输入不回显是正常现象，它与 Windows 账号密码可以不同。

若在线列表没有 `Ubuntu-24.04`，先更新 WSL，再重新查看列表；不要直接安装默认 `Ubuntu` 后假定它一定是 24.04。安装一直停在下载阶段时，可按官方文档尝试：

```powershell
wsl --install --web-download -d Ubuntu-24.04
```

已经装好该发行版时不要重复安装。检查与更新：

```powershell
wsl --list --verbose
wsl --update
```

查看 Ubuntu-24.04 所在行的 `VERSION`，应为 `2`。若为 `1`，保存工作后执行：

```powershell
wsl --set-version Ubuntu-24.04 2
```

若希望以后安装的其他发行版也默认使用 WSL2，可在 PowerShell 执行 `wsl --set-default-version 2`；它不会转换已安装的实例。出现虚拟化相关错误时，检查 BIOS/UEFI 的 CPU 虚拟化开关和 Windows“虚拟机平台”功能；学校管理的电脑应联系管理员。

更新 WSL 后保存全部 WSL 工作，再执行下面两条命令。`--shutdown` 会停止所有 WSL 发行版及其中的程序。

```powershell
wsl --shutdown
wsl -d Ubuntu-24.04
```

## 2. 确认自己位于正确的 Ubuntu

下面以及后续构建命令都在 **Ubuntu 终端**执行。

```bash
cat /etc/os-release
uname -m
dpkg --print-architecture
```

确认系统为 Ubuntu 24.04，架构分别显示 `x86_64` 和 `amd64`。Windows 任务栏上打开的 PowerShell、Ubuntu 和 QEMU 来宾终端是三个不同环境，不要互相复制执行不适用的命令。

## 3. 用 apt 安装宿主依赖

```bash
sudo apt update
sudo apt install build-essential gcc-multilib binutils gdb qemu-system-x86 qemu-system-gui python3 git curl xz-utils patch
```

| 软件包 | 在实验中的作用 |
| --- | --- |
| `build-essential` | GCC、Make 和基本 C 开发环境 |
| `gcc-multilib` | x86_64 宿主上的 32 位编译支持 |
| `binutils`、`gdb` | 汇编、链接、反汇编和调试 |
| `qemu-system-x86`、`qemu-system-gui` | 模拟 x86 机器并提供显示后端 |
| `python3` | 测试、日志分析和工具脚本 |
| `git`、`curl`、`xz-utils` | 源码管理、资产下载和解压 |
| `patch` | 把每个实验的修改应用到独立内核副本 |

不要安装旧版 GCC PPA，不要修改 `/usr/bin/gcc` 链接。仓库适配现代工具链。若 apt 报找不到包，先确认发行版、架构和软件源，再查看[排错指南](troubleshooting.md)。

## 4. 放置仓库并准备资产

把项目放在 Linux 家目录，例如 `~/source/oslab`，尽量避免 `/mnt/c`、OneDrive 或带复杂权限映射的位置。已有仓库可复制到该目录，保留隐藏文件；拿到学生发布包则在这里解压。不要照抄不存在的仓库下载地址。

```bash
mkdir -p ~/source
# 将教师发放的仓库或学生发布包放入 ~/source/oslab 后：
cd ~/source/oslab
make doctor
make prepare
```

`make prepare` 可能需要网络来获取固定版本磁盘等资产。下载缓存位于 `.cache`；资产需按套件记录的 SHA-256 校验。离线课堂应由教师提前准备同版本缓存，不能随意找一个相似镜像替换。完成准备后，按具体实验指导构建与启动。

离线准备：先在联网的同版本 Ubuntu 上完成 apt 安装与 `make prepare`，保留原始 `.cache/hdc-0.11.img`。在学生仓库创建 `.cache` 后将这个文件复制到同名位置，再执行 `make prepare`，工具会仅校验已有缓存，不联网。不要复制任何已经在 QEMU 中运行过的实验磁盘作为原始缓存。系统软件包也必须提前安装；学生压缩包不包含 apt 软件包或根文件系统。

## 5. 确认 WSLg 与 QEMU 显示

```bash
printf 'DISPLAY=%s\nWAYLAND_DISPLAY=%s\n' "$DISPLAY" "$WAYLAND_DISPLAY"
qemu-system-i386 -display help
```

环境变量和显示后端列表可帮助定位问题，但不等于已经通过图形验收。准备好实验一后，运行：

```bash
make lab1
make run-lab1
```

以实际出现的 QEMU 窗口及来宾启动画面判断。学生尚未完成系统调用时，功能测试失败并不说明 WSLg 故障。WSLg 不需要额外安装整套 Linux 桌面，通常也不需要手动设置 `DISPLAY`；曾配置外部 X Server 的同学应先检查是否有旧环境变量覆盖。

远程 SSH 或没有图形会话时，执行 `make run-lab1 QEMU_DISPLAY=curses`。QEMU 对应后端为 `-display curses`，可先用 `-display help` 确认支持。它显示 VGA 文本，不能显示所有图形模式。不要通过随意添加 `-nographic` 来判断内核能否启动：原版 Linux 0.11 不保证把控制台接到串口。

## 6. 分清三个环境

| 环境 | 运行什么 | 典型命令 |
| --- | --- | --- |
| Windows PowerShell | 安装、更新、启动 WSL | `wsl --list --verbose` |
| Ubuntu 宿主终端 | apt、Make、编辑源码、分析日志 | `make check-lab4` |
| QEMU 中的 Linux 0.11 | 旧内核用户程序、系统调用测试 | 按实验一、三、五指导执行 |

原生 Ubuntu 24.04 x86_64 用户跳过 WSL 安装，完成依赖安装和仓库准备即可；图形窗口使用原生桌面会话。不要在来宾里运行宿主的 apt 或把来宾日志路径误当作 Ubuntu 路径。
