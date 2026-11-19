# minecraft-build-design

[![CI](https://github.com/yimeng-YM/minecraft-build-design/actions/workflows/ci.yml/badge.svg)](https://github.com/yimeng-YM/minecraft-build-design/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/yimeng-YM/minecraft-build-design)](https://github.com/yimeng-YM/minecraft-build-design/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE.txt)
[![Agent Skill](https://img.shields.io/badge/Agent%20Skill-SKILL.md-8A2BE2)](https://agentskills.io)

[English](README.md)

一个 [Agent Skill](https://agentskills.io)（智能体技能），让你的 AI 编程助手为你设计**能直接粘贴进你自己世界的
Minecraft Java 版建筑**。技能里带了一套经过测试的 Python 工具包 **mcbuild**，并告诉智能体完整的工作流程：读取你世界里
的真实地形 → 确定位置 → 匹配你的风格 → 用代码设计 → 自动检查 → 交付可以直接用的文件。

可以这样说：*"在我家旁边盖个钓鱼小屋"*、*"设计一个中式亭子，放在我截图的位置"*、*"做一个 20 格宽的中世纪城门，我自己放"*。

## 你会得到

- **Litematica 投影 `.litematic`**（可选 WorldEdit/Axiom 用的 `.schem`），和真实地形对齐；或者不绑定地点、随处可放的投影；
- **离线三维预览网页**（旋转、逐层剖切、昼夜、材料清单、和你的截图前后对比）；
- **生存材料清单**（CSV）和**使用说明**（中文或英文）；
- **自动验收**：方块状态全部合法、连接与支撑正确、可站表面全部有光、每个房间都能走到（按游戏碰撞箱模拟）、不覆盖你已有的方块；
- 可选：**真实客户端粘贴测试**（打开 Minecraft，用 Litematica 粘贴后逐格比对）和带解说的**制作过程视频**。

地形可以来自单人存档、装了 **Voxy** 或 **Bobby** 去过的服务器、用 **Litematica** 另存的一片区域，或者完全没有地形。

## 需要什么

- 支持 [Agent Skills](https://agentskills.io/clients)、能运行命令行的智能体：Claude Code、Codex、Cursor、Gemini CLI、
  GitHub Copilot、OpenCode、Goose、Trae、Qwen Code、Kiro……
- **Python 3.10+**，以及 `numpy`、`Pillow`（`scripts/requirements.txt`）。
- 可选（只有用到对应功能才需要；智能体会告诉你，并在安装前征求同意）：`zstandard` + Java 17+（读 Voxy 缓存）、
  Playwright（预览截图）、JDK 21 + Litematica（游戏内实测）、ffmpeg + edge-tts + scipy（视频）。见
  `scripts/requirements-optional.txt`。
- Windows、macOS、Linux 都可以，全程离线。电脑上没装 Minecraft 也能用（预览改用地图颜色显示方块形状，方块名显示为可读的英文 ID）。

## 安装

仓库根目录**就是**技能文件夹，下面任选一种；文件夹名请保持 `minecraft-build-design`。

**1 · git clone**（推荐，之后用 `git pull` 更新）

```bash
git clone https://github.com/yimeng-YM/minecraft-build-design ~/.claude/skills/minecraft-build-design
```

把 `~/.claude/skills/` 换成你的智能体的技能目录：

| 智能体 | 个人（所有项目） | 仅当前项目 |
|---|---|---|
| Claude Code | `~/.claude/skills/` | `.claude/skills/` |
| Codex、Cline、Warp、Zed 等 | `~/.agents/skills/` | `.agents/skills/` |
| Cursor | `~/.cursor/skills/` | `.agents/skills/` |
| Gemini CLI | `~/.gemini/skills/` | `.agents/skills/` |
| GitHub Copilot | `~/.copilot/skills/` | `.agents/skills/` |
| OpenCode | `~/.config/opencode/skills/` | `.agents/skills/` |
| Trae / Qwen Code / Kiro CLI / Windsurf | `~/.trae/skills/` / `~/.qwen/skills/` / `~/.kiro/skills/` / `~/.codeium/windsurf/skills/` | `.trae/` `.qwen/` `.kiro/` `.windsurf/` 下的 `skills/` |

（路径参考 [vercel-labs/skills](https://github.com/vercel-labs/skills/blob/main/docs/agents.md)；没列出的请看对应工具的文档。）

**2 · skills 命令行**

```bash
npx skills add yimeng-YM/minecraft-build-design          # 装到当前项目；加 -g 装到所有项目
```

**3 · 发布包** —— 从 [Releases](https://github.com/yimeng-YM/minecraft-build-design/releases) 下载
`minecraft-build-design-vX.Y.Z.zip`，用 `SHA256SUMS.txt` 校验后解压到技能目录（压缩包里就是 `minecraft-build-design/`
文件夹）。Claude 应用里可以直接把这个 zip 作为技能上传；那里的代码运行在云端沙盒、读不到你的游戏，需要时把存档或投影文件发给它。

然后安装 Python 依赖并检查：

```bash
python -m pip install -r ~/.claude/skills/minecraft-build-design/scripts/requirements.txt
python ~/.claude/skills/minecraft-build-design/scripts/mcb.py doctor
python ~/.claude/skills/minecraft-build-design/scripts/mcb.py selftest
```

## 怎么用更快、更省额度

第一次使用时，智能体只会集中问一轮简单的问题，并把答案存进本机的配置文件（`~/.mcbuild/config.json`），之后的任务直接开工。
你可以提前准备：

- **建在哪**：站在要建的位置看向那里，按 **F3+C**，把复制到的那一行（`/execute in … run tp @s x y z yaw pitch`）发给它
  ——位置和视角一步到位，不用猜。或者开着 **F3** 截一张图。
- **游戏文件夹**：游戏里"选项 → 资源包 → 打开资源包文件夹"，再往上一层。单人存档："单人游戏 → 选中世界 → 编辑 →
  打开世界文件夹"。
- **在服务器上**：装了 Voxy 或 Bobby 的话，它能直接读你去过的真实地形；没有的话用 Litematica 框选那片区域另存为投影，
  并告诉它选区原点坐标。
- **较旧的游戏版本**（比如 1.20.1 / 1.21.1 整合包）：告诉它就行——投影会按你的版本写出，你的版本里没有的方块会被检查出来。

## 游戏版本

内置 **Java 1.21.11** 的方块数据。投影可以在更新的版本里直接加载（Litematica 会自动转换）。1.20.1–1.21.10 会设置目标
版本：写入对应的 DataVersion、改过名的方块用旧名字（`chain`、`grass`），并检查每个方块在你的版本里都存在。

## 隐私与安全

所有计算都在本机进行。你的存档、缓存、模组和服务器只读不写；新文件只放进项目文件夹（经你同意后，也会把投影作为新文件放进
你的 `schematics` 文件夹）。不经你同意不会下载或安装任何东西，也不会打开游戏窗口。可选的视频解说会把解说词发给微软的
TTS 服务——解说词里不会有个人信息。

## 仓库结构

```
SKILL.md                     智能体加载的说明（Agent Skills 格式）
references/                  按需阅读的详细指南
scripts/mcb.py               工具包命令行
scripts/mcbuild/             工具包（Python）、各版本方块数据、预览查看器、游戏内测试框架
LICENSE.txt, THIRD_PARTY_NOTICES.md, CHANGELOG.md, CONTRIBUTING.md
.github/                     持续集成（规范校验 + Windows/macOS/Linux 自检）和发布脚本
```

开发与发布流程见 [CONTRIBUTING.md](CONTRIBUTING.md)，更新记录见 [CHANGELOG.md](CHANGELOG.md)。

## 许可

MIT © yimeng-YM，见 [LICENSE.txt](LICENSE.txt)；第三方声明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

非 Minecraft 官方产品，未经 Mojang 或 Microsoft 批准，也与其无关（NOT AN OFFICIAL MINECRAFT PRODUCT. NOT APPROVED BY OR
ASSOCIATED WITH MOJANG OR MICROSOFT.）。本项目不包含任何游戏资源，贴图和名称都读取自你自己安装的游戏。
