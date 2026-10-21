# ContextBridge 中文快速开始

ContextBridge 把项目进度保存为本地 JSON 和 Markdown，生成适合 Codex、Claude
Code、Cursor 的交接提示词。Python 3.11+；运行时没有第三方依赖，不联网、
不调用付费 API、不上传数据、不发送遥测。

## 安装

在本项目目录中：

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install .
contextbridge --help
```

macOS/Linux 用 `source .venv/bin/activate` 激活。构建安装可能需要下载
setuptools；安装后 CLI 离线运行。完全离线且不安装时，可在仓库根目录设置
`PYTHONPATH=src`，使用 `python -m contextbridge` 代替 `contextbridge`。

## 三个命令

在需要交接的项目目录运行：

```console
contextbridge save
contextbridge transfer --to codex
contextbridge resume --to codex
```

1. `save` 填写当前任务、关键决策、失败尝试、已通过测试、已知问题、下一步。
   输入空行保留，输入 `-` 清空；列表每次输入一项。最终预览后输入 `y` 才保存。
2. `transfer` 生成新 Markdown 文件并显示路径。检查后将内容粘贴给目标 Agent，
   同时说明你现在要它做什么。可改为 `--to claude-code` 或 `--to cursor`。
3. `resume` 输出交接内容，并比较当前 Git 元数据；不会自动运行任务、测试或
   启动其他工具。已记录测试只是历史陈述，接手后需要重新验证。

所有命令都支持 `--project "D:/path/to/project"`。`save` 打印 JSON 路径，
其父文件夹名就是快照 ID；`transfer`、`resume` 可用 `--snapshot <ID>` 固定
版本，省略则选最新版本。

## 非交互使用

```powershell
contextbridge save --project "D:/path/to/project" --task "修复 Unicode 搜索" --decision "保持离线" --known-issue "尚未运行测试" --next-step "补充回归测试" --yes
contextbridge transfer --project "D:/path/to/project" --to codex
```

`--yes` 表示你已经检查摘要并允许本地保存。未运行测试时，不要写成已通过。
也可以显式指定 JSON：

```console
contextbridge save --project examples/toy-project --metadata examples/notes.json --yes
```

JSON 字段是 `task`（字符串），以及 `decisions`、`failed_attempts`、
`tests_passed`、`known_issues`、`next_steps`（字符串列表）。缺少字段会显示
未知；未知键和错误类型会被拒绝。CLI 的 `--task` 覆盖 JSON；列表参数追加。

## 安装 Codex Skill

将本仓库 `skills/contextbridge` 整个文件夹复制到目标项目的
`.agents/skills/contextbridge`。先检查目标位置，避免覆盖已有技能。
重新打开 Codex 会话后，用 `$contextbridge` 请求准备或接收交接。
Codex 执行命令的 Python 环境需要事先安装 CLI。无需覆盖 `AGENTS.md`。

## 保存位置和安全边界

数据位于指定项目的 `.contextbridge/snapshots/<ID>/context.json` 和
`context.md`；交接文档位于 `.contextbridge/transfers/`。每次创建新文件，
不覆盖旧版本。请自行把 `.contextbridge/` 加入目标项目 `.gitignore`。

默认不采集文件正文、差异正文、提交说明、作者、远程地址、环境变量或聊天
历史。敏感名称会排除，但你主动填写的自由文本不会自动脱敏，分享前需要检查。
无 Git、空仓库、分离 HEAD、脏工作区均可处理；缺少 Git 时仍可保存笔记。
Git 元数据相同不表示文件内容相同，状态没变的编辑可能无法发现。
为避免 Git 状态检查读取文件正文或触发过滤器，未暂存状态仅比较大小、时间戳和
模式，因此会保守地报告“可能修改”，也可能漏掉保留属性的编辑。敏感条目在属性
检查前排除；`dirty: null` 表示无法判断是否干净。Git 枚举未跟踪文件时会读取
仓库的 `.gitignore` 排除规则；子模块正文不检查。

这不是原生会话导入，也不携带源代码或未提交修改。换机器时，请另外带上正确
的仓库和修改，并把检查过的快照目录复制到目标项目对应位置。更多限制见
[安全说明](security.md)，GitHub 发布步骤见 [publishing.md](publishing.md)。

## 开发验证

```console
python -m pip install -e ".[dev]"
python -m pytest
python -m build
```

本次实际执行结果见 [verification.md](verification.md)。CI 配置会在推送后
运行；本地通过不能替代尚未运行的其他系统与 Python 版本检查。
