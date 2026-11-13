# 第三方来源与许可边界

本仓库的 `LICENSE` 适用于原创套件代码与文档，不覆盖以下第三方内容。

| 内容 | 固定来源与处理 |
| --- | --- |
| `vendor/linux-0.11` | [yuan-xy/Linux-0.11](https://github.com/yuan-xy/Linux-0.11)，提交 `c2e45a7f55ba61029be3b74cd7e72f23bbd068d6`。保留各源文件的 Linus Torvalds、移植者等版权注记、上游 README 与历史说明。 |
| 内核派生补丁、来宾历史 ABI 头文件 | 来自同一内核版本；`tools/guest/include` 中 errno、fcntl、signal、time、utime 和 sys 目录的历史头文件保留原文，不由套件 MIT 许可重新授权。 |
| 根文件系统 | 同一提交的 `hdc-0.11.img`，仅按固定 URL 下载到 `.cache`，不放入学生发布包；SHA-256、大小和来源见 `vendor/sources.json`。其中程序各自的版权与许可独立于本套件。 |
| `.tmp` 原实验文件 | 用户提供的课程材料，作为改写依据，不放入学生发布包。 |
| Ubuntu 软件包 | 通过 apt 安装，使用 Ubuntu 软件包自带的许可与源码渠道；本仓库不重新分发这些二进制。 |

上游仓库未提供统一的 LICENSE/COPYING 文件，因此这里不将整份历史内核或其移植代码擅自声明为 MIT 或 GPL。早期 Linux 发布的许可历史与现代 Linux 不完全相同。教学使用与公开再发布应分别核对原作者、移植者及镜像内各软件的授权；本文件记录来源，不补造缺失的授权。

本地基线变化见 [vendor/README.md](vendor/README.md)。
