# 项目初始化

> ⚠️ **执行规约（非知识文档）**。读完此文要跑 `scripts/init_project.py`，不是只"理解"套餐。
> **最小执行门**：读本节判套餐 → `python init_project.py <项目根> --type <套餐>`；需要版本化治理时加 `--init-management-git`；代码/正文/HTML 等内容生产项目优先用 `--dual-git` 或 `--init-management-git --source-workspace`；只有明确采用 legacy 外层 workspace 容器时才加 `--workspace` → 核对 `AGENTS.md` + `CLAUDE.md` / `GEMINI.md` / `HERMES.md` adapter + `.jiacong/project.json` + `.jiacong/entrypoints.json` + `topics/_seeds.md` + `doc/Framework/` → 写流水。
>
> **锚定**：SKILL.md §3.2 初始化（§1.1 结构权归用户）
> **加载时机**：新项目首次 `/jiacong-flow:smarter-project` 时，或用户要求重建脚手架时。
> **读完即应能**：选对套餐、生成正确脚手架、理解 root 标签分组与角色的差异化配置。
>
> **设计说明**：不建"根话题目录"（`topics/001_目标/card.md` 等）。`topics/` 只住讨论晶格，分组靠 frontmatter `root` 字段；成型内容走 `doc/`。套餐提供的是**推荐 root 标签清单**，落在 `topics/_seeds.md` 作为提示文件。

---

## 1 四套架构套餐

套餐是**默认建议，非硬约束**。用户可新开顶层 root 标签、混合套餐、省略目录、覆盖整套架构。

| 套餐 | 核心场景 | topics/ 定位 | vision 形态 | 推荐 root 标签数 |
|:---|:---|:---|:---|:-:|
| 📄 **学术论文** | 方法论文章 / 理论文章 / 综述 / 修稿 | 讨论性认知资产，强 | PRD 式阐释文档 | 5 |
| 📊 **实证研究** | 区域/经济/社会实证 / 量化分析 | 讨论性认知资产，中 | 研究问题+假设+数据 | 7 |
| 💻 **代码项目** | 应用开发 / 脚本工具 / 库 | 仅认知资产（架构决策/根因/设计选型） | 产品定位+核心价值 | 3 |
| 🛠️ **短平快** | 一次性任务 / 快速脚本 | 可选 | 可省略 | 0 |

**套餐选择**：与用户确认项目性质后再定。模棱两可时问"这个项目主要是写什么？"——文章选学术，数据分析选实证，代码选代码项目，一次性事情选短平快。

---

## 1.5 打开任意文件夹时的入口分类器

建档前先判断“当前打开的文件夹扮演什么角色”。这个判断先于套餐选择，也先于运行 `init_project.py`。

| 看到的文件夹状态 | 判定 | 动作 |
|:---|:---|:---|
| 有有效 `.jiacong/project.json` | 已确认项目根 | 可以运行 `health_check.py`，读取 `.jiacong/focus.json`（旧 `.claude/focus` fallback），继续当前话题 |
| 有 `.repo.git/`，且有 `main/` 或 `worktrees/` | workspace 容器 | 不在外层写 `topics/` 或 `logs/`；读取 `.jiacong-workspace/current-worktree` 定位 active project root，再检查内层是否有有效 `.jiacong/project.json` |
| 位于 `main/` 或 `worktrees/<branch>/`，但没有有效 `.jiacong/project.json` | worktree 候选根 | 只能作为候选；即使有 `.git`、`.claude/CLAUDE.md`、`topics/` 或 `logs/`，也不能直接进入治理 |
| 当前目录有 `.git`，但没有有效 `.jiacong/project.json` | 既有 Git 项目候选根 | 默认原位建档：`python scripts/init_project.py <项目根> --type <套餐>`；不要自动改造成 workspace |
| 当前目录无 `.git`、无 `.claude/topics/logs`，且为空 | 新项目候选根 | 先建立标准管理根；需要版本化治理时加 `--init-management-git`，需要内容层独立 Git 时加 `--source-workspace`，推荐双层 Git 可用 `--dual-git` |
| 当前目录无 `.git`、无 `.claude/topics/logs`，但已有历史文件 | 普通历史文件目录 | 若采用标准项目根，原位 init；若采用 workspace 容器并希望历史文件进入 `main/`，显式使用 `--workspace --adopt-existing` |
| 只有 `.claude/`、`topics/`、`logs/` 中的一部分 | 半建档/旧结构 | 停止自动初始化；先做体检或迁移判断，避免覆盖状态源 |
| 父目录下有多个子 `.git` 仓库 | 多 repo 工作区 | 不自动选择父目录建档；先选定具体项目根，或建立明确的 workspace 容器规则 |
| 同一层同时出现 `.git` 与 `.repo.git` | 混合 Git 模式 | 停止自动初始化；先确定保留标准 repo 还是 workspace-orchestrator |

**优先级**：有效 `.jiacong/project.json` 已确认项目根 > workspace active project root（且 active root 有有效 `.jiacong/project.json`）> 既有 `.git` 项目候选根 > 普通新项目候选根。workspace 是多 worktree 编排模式，不是所有项目的默认 Git 形态。

**授权边界**：`.claude/CLAUDE.md`、`AGENTS.md`、`GEMINI.md`、`topics/`、`logs/` 只说明存在入口或旧项目管理痕迹；它们不能替代 `.jiacong/project.json`，也不能单独启用治理。

**脚本边界**：`init_project.py --workspace` 会拒绝已经存在 `.claude/`、`topics/` 或 `logs/` 的目录；`--adopt-existing` 会拒绝已有 `.git` 的目录。多 repo、混合 Git、半建档痕迹需要 AI 按上表先说明风险并征求迁移决策。

**源码层 workspace 决策**（推荐用于代码/正文/HTML 等内容生产项目）：

内容生产项目如果需要让治理记录与交付物历史分离，优先使用管理根 Git + 源码层 workspace。管理根承载 `.jiacong/`、`topics/`、`logs/`、`doc/Framework/` 和入口文件；源码层承载 `app/`、`src/`、正文、HTML 或其他产物。推荐命令：

```bash
python scripts/init_project.py <项目根> --type 代码 --dual-git --source-dir app
```

等价显式写法：

```bash
python scripts/init_project.py <项目根> --type 代码 --init-management-git --source-workspace --source-dir app
```

生成形态：

```text
<项目根>/
├── .git/          # 管理层 Git：治理记录与入口文件
├── .jiacong/
├── AGENTS.md
├── CLAUDE.md / GEMINI.md / HERMES.md
├── topics/
├── logs/
├── doc/Framework/
└── source/
    ├── .repo.git
    ├── main/app/
    └── worktrees/
```

`--dual-git` 等价于 `--init-management-git --source-workspace`。`--source-workspace` 与 `--workspace` 互斥。启用源码层 workspace 时，管理根不再创建代码套餐中的 `src/`，源码层按 Git 原生 worktree 布局生成在 `source/` 下。`.jiacong/source.json` 只记录源码层布局元数据；它不是治理授权，也不是当前源码目录指针。治理授权仍然只看 `.jiacong/project.json`，代码操作以当前 cwd、用户显式路径或 Git worktree 现场为准。

**legacy workspace 模式下的源码子仓库决策**（`--workspace --source-dir`）：

当入口分类器判定为 legacy workspace 容器后，需进一步判断源码放在哪里。父仓库（`.repo.git`）管项目管理状态（`.jiacong/`、`topics/`、`logs/`、`doc/Framework/`），子仓库管源码（`install.py`、`hooks/`、`skills/` 等），推 GitHub 时只推子仓库内容。

| 场景 | 判定 | 动作 |
|:---|:---|:---|
| workspace + 源码在子目录（如 `app/`、`src/`） | 需要源码子仓库 | `--source-dir <子目录名>`，脚本自动 `git init` 子目录 |
| workspace + 根目录即源码 | 不需要源码子仓库 | `--source-dir .`，跳过子仓库初始化 |
| workspace + 已有源码子目录 + 已有 `.git` | 已有子仓库 | 跳过子仓库初始化，检查 `.git` 是否正常 |

**子仓库推远程流程**（`git subtree split`）：
```bash
cd <workspace>/main
git subtree split --prefix=<source-dir> -b deploy-app
git push origin deploy-app:main --force
```

---

## 2 三层目录分层原则

所有套餐共同遵守：

| 层 | 目录 | 性质 | 装什么 |
|:---|:---|:---|:---|
| **项目元层** | `.jiacong/` | 项目确认、入口关系、焦点、缓存和派生视图 | project.json / entrypoints.json / focus.json / dashboard/ / cache/ |
| **讨论层** | `topics/` | 推理过程 + 决策记录 | NNN_简称/{scratch, card, tasks}（纯讨论晶格，按 root 字段分组） |
| **内容层** | `doc/`（默认位）+ `results/` 等 | 项目本身的文档或产物 | 成型档案 / 正稿 / 实证结果 |
| **认知基础设施** | `base/` | 跨话题共用的思维资源 | `perspectives/`（视角卡）· `resources/`（素材矿/参考材料，含外部知识载体与检索线索）· `tools/`（加工手段）· `disposition/`（布局/布阵） |
| **人类涂鸦区** | `draft/` | 用户自由创建，AI 只读 | 核心理念、灵感碎片、未归类想法 |

辅助目录按需：`logs/`（时间流）、`archive/`（旧版本，**不装终态 card**）。

**源码承载三形态**：标准代码项目默认用 `src/`（或用户指定的 `app/`、`lib/`）承载源码；启用 `--source-workspace` 时，管理根不建 `src/`，源码层进入 `source/`，`.jiacong/source.json` 只记录 `source_root`、`repo_git_path`、`worktrees_root`、`main_name`、`source_dir` 等布局元数据，不维护 active 指针；legacy `--workspace --source-dir` 则在 `main/<source-dir>` 初始化源码子仓库，外层 `.repo.git` 仍管管理层 worktree。

**归宿判据**（决定新产物落哪层）：

- 需讨论的流程/决策/辩论 → `topics/`（子话题目录）
- 读者用的成型参考 → `doc/`（默认位）或 `results/`（套餐特色目录）
- 思维框架 / 素材与参考材料（含外部检索线索） / 工具 / 布局 → `base/`（perspectives / resources / tools / disposition）
- 跨项目可复用的规范 → skill 的 `references/` 或用户级 CLAUDE.md
- 项目内元层文件 → `.jiacong/`；Claude 专属 hook 配置才进入 `.claude/`

**判据细化**（topics/ vs doc/）：
- 是否还需讨论/修订？是 → `topics/`；否 → `doc/`
- 是否作为正式交付物给读者？是 → `doc/`；否 → `topics/`
- 讨论-沉淀双态：`topics/NNN/card.md` 的结论段落成熟后，迁入 `doc/` 作为成文（card 正文留指针）

---

## 3 各套餐差异

### 3.1 学术论文

```
<项目根>/
├── .jiacong/              # 项目元层
├── topics/               # 讨论层（纯讨论晶格，按 root 字段分组）
│   ├── _seeds.md         # 推荐 root 标签清单（提示文件）
│   └── _tree.md          # 话题树（mermaid + ASCII）
├── doc/                  # 内容层（成型文档）
├── manuscript/           # 产物层：论文手稿（按章节组织）
├── draft/                # 人类涂鸦区（AI 只读）
├── logs/stream.md        # 流水
└── base/                 # 认知基础设施
    ├── perspectives/     # 视角：思维框架、高手模式、角色卡
    ├── resources/        # 资源：素材矿、参考材料与外部检索线索
    ├── tools/            # 工具：加工手段
    └── disposition/      # 布局：行动者、场域、连接动作的布阵关系
```

**推荐 root 标签 5 个**：🎯目标 / 🧠论证 / ✍️写作 / 🛠️管理 / 📚文献。

### 3.2 实证研究

在学术套餐基础上追加（去掉 `manuscript/`，增加数据/模型/结果/笔记本）：

```
<项目根>/
├── .jiacong/              # 项目元层
├── topics/               # 讨论层（同学术套餐结构）
│   └── _seeds.md         # 7 个推荐标签
├── doc/                  # 内容层
├── draft/                # 人类涂鸦区（AI 只读）
├── data/                 # 原始数据（.gitignore）
├── models/               # 模型定义
├── results/              # 分析产物
├── notebooks/            # 分析笔记本
├── logs/stream.md        # 流水
└── base/                 # 认知基础设施
    ├── perspectives/     # 视角卡
    ├── resources/        # 资源：素材矿、参考材料与外部检索线索
    ├── tools/            # 加工手段
    └── disposition/      # 布局：行动者、场域、连接动作的布阵关系
```

**推荐 root 标签 7 个**：学术 5 个 + 📊数据 + 🧮模型。

### 3.3 代码项目

```
<项目根>/
├── .jiacong/
├── AGENTS.md
├── CLAUDE.md / GEMINI.md / HERMES.md
├── topics/               # 仅装讨论性认知资产（架构决策/根因/设计选型）
│   └── _seeds.md         # 3 个推荐标签
├── doc/                  # 阶段文档（四大基础话题的 doc 映射统一落此）
├── draft/                # 人类涂鸦区（AI 只读）
├── src/                  # 产物层：源码
├── logs/stream.md        # 流水
└── base/                 # 认知基础设施
    ├── perspectives/     # 视角卡
    ├── resources/        # 资源：素材矿、参考材料与外部检索线索
    ├── tools/            # 加工手段
    └── disposition/      # 布局：行动者、场域、连接动作的布阵关系
```

**推荐 root 标签 3 个**：🏗️架构 / 🧠设计 / 🛠️工具。

**doc/ 与基础话题的关系**：`doc/structure.md` 在代码项目中就是 code-map（代码结构地图），`doc/style.md` 就是视觉锚点映射——内容语义由基础话题的差异化 TOC 定义，不另建子目录。

**src/ 分离原则**：标准代码项目中，源码/应用代码放 `src/`（产物层），项目过程文件（topics/logs/doc/base）放外层。两层分离避免 git 跟踪范围与项目管理文件冲突。`src/` 目录名可按项目实际情况调整（如 `app/`、`lib/`）。

**源码层 workspace 变体**：代码项目需要源码 Git/worktree 与管理根彻底分离时，使用 `--source-workspace --source-dir app`。此时结构变为：管理根保留 `.jiacong/`、`topics/`、`logs/`、`doc/Framework/` 和入口文件；源码层生成 `source/.repo.git`、`source/main/app/` 与 `source/worktrees/`。该模式下管理根不创建 `src/`，`--source-dir .` 被拒绝，`--no-source-git` 会只创建 `source/main/<source-dir>/` 目录骨架、不创建 `source/.repo.git`，并在 `.jiacong/source.json` 写入 `git_enabled: false`。`.jiacong/source.json` 不维护当前源码 worktree；多分支并行操作由 Git worktree、当前 cwd 与显式路径决定。

**关键区别**：代码项目不给常规开发流程建话题卡，只在出现**值得讨论的设计选型或架构决策**时建。日常 bug 修复走 git commit + doc/，不走 topics/。

### 3.4 短平快

```
<项目根>/
├── .jiacong/              # 项目元层
├── doc/                  # 内容层（产出落位）
├── draft/                # 人类涂鸦区（AI 只读）
└── logs/stream.md        # 可选
```

vision 可省略，`topics/` 初期可空。项目入口仍是 `AGENTS.md`；短任务清单进入 `doc/` 或 `logs/stream.md`。

---

## 4 初始化执行

先走 §1.5 入口分类器，再运行下面命令。不要在未判定文件夹角色时直接初始化。

```
python scripts/init_project.py <项目根> --type <套餐>
```

`--type` 可选：`学术` / `实证` / `代码` / `短平快`。

代码项目若要按当前推荐的“管理层 Git + 源码层 workspace”运行：

```
python scripts/init_project.py <项目根> --type 代码 --dual-git --source-dir app
```

显式写法：

```
python scripts/init_project.py <项目根> --type 代码 --init-management-git --source-workspace --source-dir app
```

源码层 workspace 模式下，`<项目根>` 是唯一管理根，承载 `.jiacong/`、`topics/`、`logs/`、`doc/Framework/`；加 `--init-management-git` 或 `--dual-git` 时，项目根 `.git` 负责治理层版本历史。源码层在 `source/` 下按 Git worktree 布局生成。`--source-root`、`--source-dir`、`--source-main-name` 只能是项目内安全相对路径，禁止绝对路径和 `..`；`--source-workspace` 与 `--workspace` 互斥。需要先禁用源码 Git 时可加 `--no-source-git`，脚本仍会写 `.jiacong/source.json`，其中 `git_enabled=false`。

若项目明确需要 legacy“外层 workspace 容器 + 内层 main/worktrees 项目根”运行：

```
python scripts/init_project.py <workspace根> --type <套餐> --workspace
```

`--workspace` 是旧管理层 workspace 兼容模式，不作为新项目默认推荐。新项目优先用标准管理根；需要双层 Git 时用 `--dual-git`。

legacy workspace 模式的外层只承载 Git/worktree 路由与多 CLI 容器入口，不承载 `topics/` 或 `logs/`。真实建档会写入 `main/`，并把 `.jiacong-workspace/current-worktree` 初始化为 `main`。后续 feature/refactor 分支放入 `worktrees/<branch>/`，由 workspace active worktree 选择当前项目现场。

CLI hook 文件按宿主协议分开：Claude 写 `.claude/settings.local.json`，Codex 写 `.codex/hooks.json`，Gemini 写 `.gemini/settings.json`。Gemini 不使用 `UserPromptSubmit/PostToolUse/Stop` 事件名，而是映射到 `BeforeAgent/AfterTool/AfterAgent`。

生命周期上，active 切换与归档由外层 `app/workspace_use.py` 管理：

```
python app/workspace_use.py --workspace <workspace根> list
python app/workspace_use.py --workspace <workspace根> use <branch>
python app/workspace_use.py --workspace <workspace根> archive <branch> --dry-run
python app/workspace_use.py --workspace <workspace根> archive <branch>
```

`archive` 要求目标不是 `main`、不是当前 active worktree、且 `git status --porcelain` 为空。默认流程是：复制目标 worktree 文件到 `.jiacong-workspace/archive/branches/<branch>/<timestamp>/snapshot/`（不复制 `.git`）、创建 `archive/<branch>/<timestamp>` tag、执行 `git worktree remove`、删除本地 branch；如需保留 branch，加 `--keep-branch`。恢复命令写在同目录 `metadata.json` 的 `restore` 字段。

若当前目录是**无 git、无 `.claude/topics/logs` 的历史文件目录**，并且希望把这些历史文件作为 `main/` 的项目内容，可显式加：

```
python scripts/init_project.py <workspace根> --type <套餐> --workspace --adopt-existing
```

`--adopt-existing` 会先建立 workspace/main 骨架，再把外层已有文件和目录移动进 `main/`。默认不移动任何历史文件；检测到 `.git`、`.claude/`、`topics/` 或 `logs/` 时停止，避免破坏既有仓库或已建档项目。

脚本产出：
- 按套餐建目录（含 `doc/` 内容层与 `base/` 基础设施）
- 写项目级 `AGENTS.md` canonical 入口，并写 `CLAUDE.md` / `GEMINI.md` / `HERMES.md` adapter 指回 `AGENTS.md`
- 写 `.jiacong/project.json` 与 `.jiacong/entrypoints.json`
- 用户显式加 `--init-management-git` 或 `--dual-git` 时，在项目根初始化普通 `.git` 作为管理层 Git
- 写 `topics/_seeds.md` 列出推荐 root 标签 + 示范 `topic_new.py` 命令
- 写 `topics/_tree.md` 占位（初始无节点）
- 不默认创建 `.claude/`；仅在安装 Claude hook 配置或保留既有 legacy fallback 时使用 `.claude/`，不默认生成 `.claude/CLAUDE.md`
- Framework 文件迁入 `doc/Framework/`，Vision / Structure / Style / Trace 作为项目级最高压缩层
- 建 `.gitignore`（含 `.jiacong/cache/`、`.jiacong/dashboard/` 与 watcher/round 等派生/运行态忽略）
- 扫描旧版根话题目录（若存在）并报告迁移建议（不自动改动）

初始化完成后提示用户跑：

```
python scripts/tree_gen.py <项目根>
python scripts/dashboard.py <项目根>
```

---

## 4.5 双 Git / 源码层 workspace 边界

这里的“双 Git”指管理层 Git 与内容/源码层 Git 分工，不是简单在两个目录里都执行 `git init`。

- 管理层 Git：管理 Jiacong Flow 项目治理材料，如 `.jiacong/`、`topics/`、`logs/`、`doc/Framework/`、入口文档与项目记录。
- 内容层 Git：管理实际源码或产物历史，如 `source/.repo.git`、`source/main/<source_dir>/`、`source/worktrees/`。

当前 `--dual-git` 实现完整推荐组合：项目根普通 `.git` 是管理层 Git，负责 `.jiacong/`、`topics/`、`logs/`、`doc/Framework/`、入口文档与项目记录；`source/.repo.git` 是内容层 Git，负责 `source/main/<source_dir>/` 与 `source/worktrees/` 中的源码、正文、HTML 或其他交付物。

这更接近 Google/Android `repo` tool 一类实践中的“上层管理/manifest + 下层内容仓库”分层思想：上层负责把项目结构、索引和工作入口组织起来，下层仓库负责源码提交历史。Jiacong Flow 的边界更克制：它不维护多仓 manifest，不替用户切 active 源码目录，不给内容仓库做统一同步命令。Jiacong Flow 只声明源码层布局；具体代码操作由当前 cwd、用户显式路径和 Git 原生 worktree 现场决定。

---

## 5 默认角色克隆

初始化时询问用户是否从 skill 全局角色库克隆默认视角卡：

- 学术套餐 → 推荐克隆 academic/ methodology/ writing/ 下全部
- 实证套餐 → 推荐克隆 methodology/ + 按需加统计类
- 代码项目 → 推荐保持空 `base/perspectives/`，按需新建
- 短平快 → 不克隆

用户批准 → 走 `role_manager.py` 克隆通道（见 `roles-ops.md` §4）。

---

## 6 项目入口初始内容

`AGENTS.md` 是项目管理 canonical 入口；`CLAUDE.md` / `GEMINI.md` / `HERMES.md` 是 adapter，指回 `AGENTS.md`。`templates/project/project_entry.md.tmpl` 作为项目入口正文模板，应描述项目对象、Framework、`.jiacong/` 元数据与文件索引，不再以 Claude 专属入口为中心。

入口骨架包含：

- 头部三行：项目名 / 项目类型 / 最后更新 / smarter-project 加载标记
- `## 🎯 项目理想样态`（活文档，按套餐差异化占位：学术=问题/主张/读者/边界/验收画像；实证=研究问题/数据/方法/预期结论/边界；代码=产品定位/核心能力/技术路线/验收画像/边界；短平快=一句话目标/验收）
- `## ✅ 验收标准`（活文档，"目标即标准"，顶层维护）
- `## 📍 当前焦点`（指向 `.jiacong/focus.json`，由 `focus_breadcrumb.py` 渲染面包屑，旧 `.claude/focus` fallback）
- `## 🔥 近期话题`（指向 `.jiacong/dashboard/index.html`，由 `active_topics.py` + `dashboard.py` 生成）
- `## 📊 仪表盘`（话题树 / 健康警告 / 生成命令）
- `## 📜 流水`（指向 `logs/stream.md`，含 `health_check.py` 阈值说明）
- `## 🔭 认知基础设施`（指向 `base/`，说明 perspectives / resources / tools / disposition 四类归位，含套餐推荐的 root 标签清单）
- `## 📁 文件索引`（项目根目录树）

骨架字段默认留 `（待填）`，由用户在首轮对话中与 AI 对齐后填充。**理想样态与验收标准是活文档**——随项目推进迭代维护，不是一次写定。

---

## 7 混合与覆盖

用户可：
- **混合 root 标签**：在学术基础上加 📊数据（不切整套实证）
- **删减目录**：短平快上不建 `topics/`
- **新开顶层 root 标签**：超出套餐预设的主题

套餐只是启动条件，项目长期演进由实际需求驱动。
