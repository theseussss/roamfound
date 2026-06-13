---
description: 同步 jiacong-flow 到 Claude Code / Codex / Gemini CLI / Hermes Agent 入口（幂等注入）
allowed-tools: Bash
---

# jiacong-flow · 同步多 CLI 入口

Claude Code 模式把 plugin 里 `protocol-fragments/` 下的 8 个 fragment（identity-check / env-verify / startup-align / language / interaction-protocol / map-feedback / edit-levels / jailbreak）注入用户级 `~/.claude/CLAUDE.md`。

Codex 模式把 jiacong-flow 全局入口注入 `~/.codex/AGENTS.md`，并把 `skills/*/` 下的并列 skills 安装到 `~/.codex/skills/<skill-name>`。

Gemini CLI 模式把 jiacong-flow 全局入口注入 `~/.gemini/GEMINI.md`，并把 `skills/*/` 下的并列 skills 安装到 `~/.gemini/skills/<skill-name>`。

Hermes Agent 模式把 jiacong-flow 协议片段注入 `~/.hermes/SOUL.md`，把自包含插件链接到 `~/.hermes/plugins/jiacong-flow`。Hermes hooks 由插件 `plugin.yaml` 声明，不额外写用户级 hook 配置。

## 职责边界

`/jiacong-flow:setup` 只负责同步 CLI 入口。Claude Code 的命令补全与 skill 入口由 `.claude-plugin/plugin.json` 的 `commands` / `skills` 声明负责；如果输入 `/jia` 看不到候选，先更新并重载插件，再运行 setup。

## 执行

Claude Code 默认（实际写入）：

```bash
python "${CLAUDE_PLUGIN_ROOT}/install.py" --agent claude
```

预览（只报告变更不写文件）：

```bash
python "${CLAUDE_PLUGIN_ROOT}/install.py" --agent claude --dry-run
```

指定目标文件（非默认路径）：

```bash
python "${CLAUDE_PLUGIN_ROOT}/install.py" --agent claude --target <path>
```

Codex 全局入口：

```bash
# 在 plugin 根目录执行
python install.py --agent codex --dry-run
python install.py --agent codex

# 在 Claude Code plugin command 上下文执行
python "${CLAUDE_PLUGIN_ROOT}/install.py" --agent codex --dry-run
python "${CLAUDE_PLUGIN_ROOT}/install.py" --agent codex
```

Gemini CLI 全局入口：

```bash
python install.py --agent gemini --dry-run
python install.py --agent gemini

python "${CLAUDE_PLUGIN_ROOT}/install.py" --agent gemini --dry-run
python "${CLAUDE_PLUGIN_ROOT}/install.py" --agent gemini
```

Hermes Agent 全局入口与插件：

```bash
python install.py --agent hermes --dry-run
python install.py --agent hermes

python "${CLAUDE_PLUGIN_ROOT}/install.py" --agent hermes --dry-run
python "${CLAUDE_PLUGIN_ROOT}/install.py" --agent hermes
```

多 CLI 同步：

```bash
python install.py --agent claude,codex,gemini,hermes
python install.py --agent all --dry-run
python install.py --agent all
python install.py --list-agents
```

## 参数判断

- 用户说"预览 / 先看看 / dry run / 不要真写"→ 加 `--dry-run`
- 用户没指定 → Claude Code 默认模式（实际写入）
- 用户明确说 Codex → 加 `--agent codex`
- 用户明确说 Gemini → 加 `--agent gemini`
- 用户明确说 Hermes → 加 `--agent hermes`
- 用户明确说多个 CLI → 用逗号组合，如 `--agent claude,codex,gemini,hermes`
- 用户明确说全部 CLI → 加 `--agent all`
- 用户给了具体路径 → 加对应 agent 的 `--target <path>`

## Python 路径

如果目标机器 `~/.claude/CLAUDE.md`、`~/.codex/AGENTS.md`、`~/.gemini/GEMINI.md`、`~/.hermes/SOUL.md` 或项目级入口文件里规定了具体 Python 路径（例如 `D:/01Software/01VibeCoding/Python/python.exe`），用它；否则用 PATH 里的 `python` 或 `python3`。

## 幂等保证（install.py 内置）

- Claude marker 块已存在 → update 内容（不会重复插入新块）
- Codex 入口 marker 已存在 → update 内容；不存在 → append 到 `~/.codex/AGENTS.md`
- Gemini 入口 marker 已存在 → update 内容；不存在 → append 到 `~/.gemini/GEMINI.md`
- Hermes SOUL marker 已存在 → update 内容；不存在 → append 到 `~/.hermes/SOUL.md`
- Hermes plugin symlink 已存在且指向当前插件 → current；指向旧位置 → relink；普通目录冲突 → warning，不自动覆盖
- 全部入口都无变更 → 不写文件、不生成备份
- 任一入口有变更 → 写入前自动备份为 `<target>.YYYYMMDD-HHMMSS.bak`；同秒连续操作追加 `.2`、`.3` 等序号，不覆盖旧备份

手工改 marker **外**的内容不会被 install.py 触碰；marker **内**的手改会被下次 install 覆盖。

## 报告

执行后把命令原始输出原样展示给用户，让用户看到每个 action：

- ✅ `update` — marker 已存在，内容已更新
- ✅ `inserted` — marker 不存在，按 `insert_after_section` / `insert_after_line_match` 插入到指定位置
- ✅ `appended` — marker 不存在，按 `append_eof` 附加到文件末尾
- ✅ `linked` / `copied` / `current` — Codex/Gemini skill 已安装
- ✅ `hermes_plugin: linked/current/relinked` — Hermes 自包含插件已就位
- ⚠️ `warning` — 插入锚点未找到、skill 已存在但指向其他位置，需检查

如果出现 ⚠️ warning，提醒用户检查目标文件结构或既有同名 skill 指向。
