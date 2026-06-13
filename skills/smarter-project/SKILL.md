---
name: smarter-project
description: 项目管理执行规约。焦点检查驱动每轮循环（话题识别→角色→执行→记录），话题化组织认知，三件套分层沉淀，脚本保证结构一致。
---

# smarter-project

> ⚠️ **执行规约（非知识文档）**。读完要跑脚本、要写 scratch，不是只"理解"。

你在一个项目中和用户反复对话，讨论会产生大量认知碎片。如果这些碎片散落在对话历史里，下次开会话时它们就消失了。smarter-project 解决的就是这个问题——把讨论中产生的认知组织成可持久、可检索、可继续推进的结构。

做法是**话题化**：每一个值得追踪的讨论方向，都开一个话题目录（`topics/NNN_简称/`），里面放**三件套**——

| 文件 | 性质 | 承载 |
|:---|:---|:---|
| `scratch.md` 讨论卡 | 每轮追加，不删不清 | 原始讨论过程——"当时怎么想的" |
| `card.md` 话题卡 | 唯一真理源 | 从讨论中提炼的结构化结论 |
| `tasks.md` 任务卡 | 可选 | 从话题派生的执行步骤 |

基础话题卡（`base_topic: true`）可选生成第四组件 `template.md`，承载建构说明、可重复单元模板与地图渲染约定。普通话题默认三件套，需要时通过 `--with-template` 生成。详见 `references/base-topic-templates.md`。

话题文件夹里也允许放额外文件（诊断报告、方案草稿等），但必须在 scratch 对应条目中索引，确保能追溯来源。

每个文件顶部有 YAML frontmatter（`topic_id`、`status`、`parent`、`root` 等）。card.md 以 frontmatter `toc:` 为唯一结构源（格式与约束详见 §2.1 话题），正文 `## 📑 本卡目录` 只是由脚本渲染的只读视图。status 标记生命周期阶段，完整流转判据见 `references/topic-lifecycle.md`。

全部状态落在 markdown 文件中，不做数据库，打开编辑器就能审计。Python 脚本（`scripts/*.py`）负责建话题、校验结构、生成可视化等操作——AI 必须调用脚本，禁止手工 mkdir + 手写文件替代，因为脚本才能保证格式一致。

现有 HTML 仪表盘（`dashboard.html`、`role_manager.html`、`_tree.md` 可视化）是未来统一 GUI 的理念基石。

下面按实际执行流来组织。`<skill>` = `${CLAUDE_PLUGIN_ROOT}/skills/smarter-project`。

| § | 内容 | 管什么 |
|:-:|:---|:---|
| 1.1 | 总纲 | 全局设计原则 |
| 1.2 | 会话启动 | 判断是否建项目、体检、首段输出 |
| 1.3 | 每轮循环 | 焦点检查 → 角色 → 执行 → 写 scratch |
| 2.1 | 话题 | 三件套的建、改、迁移、收敛、额外文件 |
| 2.2 | 记录机制 | scratch / log / tasks.md / Trace（追踪）话题四层分工 |
| 3.1 | 角色 | 蒸馏高手，视角一以贯之 |
| 3.2 | 初始化 | 套餐 + 基础话题卡集 |
| 4 | 审查 | 结构对齐与一致性检查 |

---

## §1.1 · 总纲

三条全局原则，贯穿后续所有章节。

**md 唯一真理源。** 讨论与结论状态在 markdown 文件的 frontmatter 和正文中；项目运行态、缓存和派生视图默认落在 `.jiacong/` 下，可删除重建。不做数据库、不做双写。旧 `.claude/` 只作 Claude hook 配置或 legacy fallback。

**结构权归用户。** 结构变更——改 TOC、增删章节、新建话题、偏离套餐——由 AI 提议、用户审批。内容填充（在已有章节内写正文）由 AI 动笔、用户校对。用户未明确批准的提议一律视为拒绝：有效批准词是"同意/通过/可以/就这样/对/行/OK/去做/开搞"；含糊回复（嗯/哦/知道了/好）须追问确认。

**脚本优先。** 凡有对应脚本的操作，AI 必须调用脚本。手工替代是最常见的执行偏差来源。

---

## §1.2 · 会话启动

会话第一轮有一个额外判断：这个对话需不需要项目管理？

如果用户只是随手问个问题、做个一次性查询，skill 不介入，直接回答。如果任务涉及多轮协作、需要持久化认知（论文写作、方案设计、代码项目等），就需要建档。不确定时，问用户。

建档前必须先做**入口分类**：当前打开的文件夹究竟是标准 `.git` 项目根、workspace 容器、workspace 内 worktree、无 git 历史文件目录、多 repo 工作区，还是半建档旧结构。分类规则见 `references/init-project.md §1.5`。未完成入口分类前，不直接运行初始化脚本。

确定需要建档后：

```
项目存在吗？
├─ 有有效 .jiacong/project.json → health_check 脚本
│  检查结构合规 + 三件套完整性
│    │
│    ▼
│  读 AGENTS.md → 读 `.jiacong/focus.json` → 建焦点面包屑 → 输出首段
│  焦点为空 → 提示用户选话题
└─ 没有有效 .jiacong/project.json → 先做入口分类
   ├─ 用户确认建档 → init 脚本（§3.2 初始化）
   │  写确认标记 + 建脚手架 + 基础话题卡集
   └─ 旧痕迹/候选目录 → 只提示风险与迁移方案，不启用治理
```

**RUN**

| 场景 | 命令 |
|:---|:---|
| 建档入口分类 | 先读 `references/init-project.md §1.5` |
| 新项目 | `python "<skill>/scripts/init_project.py" <根> --type <套餐>` |
| 代码项目 + 源码层 workspace（推荐） | `python "<skill>/scripts/init_project.py" <根> --type 代码 --source-workspace --source-dir app` |
| legacy workspace 容器 | `python "<skill>/scripts/init_project.py" <workspace根> --type <套餐> --workspace` |
| 无 git 历史文件目录转 legacy workspace | `python "<skill>/scripts/init_project.py" <workspace根> --type <套餐> --workspace --adopt-existing` |
| legacy workspace + 源码子仓库 | `python "<skill>/scripts/init_project.py" <workspace根> --type <套餐> --workspace --source-dir app` |
| 已有项目体检 | `python "<skill>/scripts/health_check.py" <根> --json` |
| 焦点非空 | `python "<skill>/scripts/focus_breadcrumb.py" <根>` |
| 焦点为空 | 提示用户选话题 |
| 仪表盘不存在 | `python "<skill>/scripts/dashboard.py" <根>` |

---

## §1.3 · 每轮循环

从第二轮开始，每轮对话走同一个循环：

```
用户消息 → ① 焦点检查 → ② 角色确认 → ③ 执行回复 → ④ 写 scratch → ⑤ Framework 更新检查
```

### ① 焦点检查

这是整个 skill 的核心引擎。每轮用户消息提交时，`UserPromptSubmit` hook 通过 `hookSpecificOutput` JSON 协议（stdout）自动注入当前焦点状态和话题线索到 AI 上下文。AI 基于注入的焦点信息判断：**用户这条消息还在聊同一个话题吗？**

如果是，继续当前话题，输出一行短面包屑即可：

```
当前位置：父话题 > 当前话题:TNN
层级判断：独立 / 下属 / 支线 / 延续当前焦点
本轮归位：scratch / card / tasks / doc / 无写入
```

如果不是——无论是用户主动提出新话题，还是讨论中自然浮现了新方向——AI 需要处理话题转换。具体怎么处理取决于 AI 的判断自信度：自信这确实是新话题，就直接用 `topic_new.py` 建话题并切焦点；不太确定的话，先向用户提议，等确认后再建。如果用户说"这个先不展开"，就标记但不切焦点——不过下轮如果用户的问题其实属于那个新话题，焦点检查会自动识别并切换。

话题切换时有两件事要做：旧话题签退（从 scratch 汇总写入 log）和新话题签到（在 log 预写开放条目）。详见 §2.2 记录机制。

如果当前话题 status 仍为 ⏳进行中，切换前输出警告——切走意味着冻结上下文，下次回来要重建认知现场：

```
⚠️ 焦点切换请求
当前焦点 [当前ID] 未完成。
切换后果：当前推导上下文将冻结，下次切回需重建认知现场。
若仍要切换，请明确回复：切换到 [目标ID]
```

### 侧写：不切焦点的跨话题更新

焦点检查有时会发现：当前讨论触及了另一个话题，但不值得切焦点——只需要在那边记一笔。这就是**侧写**（side-write）。侧写解决的问题是：严格的单焦点假设会导致跨话题信息丢失，但频繁切焦点又会打断推理连续性。

三个层级，从轻到重：

| 层级 | 动作 | 示例 |
|:---|:---|:---|
| **只读** | 发现关联但不操作 | "这和 T05 有关，先记着" |
| **侧写** | 在目标话题 scratch 追加简短条目，不切焦点 | 更新状态、补充一条发现、标记待办 |
| **切焦点** | 需要展开讨论或改结构 | 进入目标话题深入推进 |

侧写时，当前话题的 scratch 记录侧写动作（`→ 侧写 T05：补充了 XX`），目标话题的 scratch 记录来源（`← 来自 T03/S012：XX`）。双向索引保证可追溯。

Trace（追踪）话题（见 §2.2 记录机制）天然是侧写的汇聚点——多个话题的进展都可能需要在 Trace 话题上记一笔。

### ② 角色确认

视角应当一以贯之。如果当前已有角色且话题域没变，保持即可。如果需要新角色，从角色库选取或当场建一个——理念是蒸馏该领域最强大脑的思维方式（详见 §3.1 角色）。没有角色也是一种选择，更开放但可能更平庸，坦诚声明就好。

### ③ 执行回复

读取当前话题上下文，执行任务，需要跑脚本时调用。

如果本轮是复杂提案、架构方案、方法论设计、决策备忘、研究综述、证据依赖判断，或 skill / plugin / agent 设计，调用并列 skill `one-turn-proposal`；桥接规则见 `references/proposal-bridge.md`。`one-turn-proposal` 只负责回答结构、方法论和证据治理，项目写入仍回到 scratch/card/tasks 与现有脚本。

### ④ 写 scratch

每轮必做。在当前话题的 scratch.md 追加一条带编号的条目，记录本轮讨论了什么。如果本轮产出了额外文件，在同一条目中索引文件名和路径。格式见 §2.2 记录机制。

### ⑤ Framework 更新检查

每轮都要提醒并检查 Framework，无论本轮是否已经满足实际更新条件。检查不是自动修改 `doc/Framework/`，而是判断本轮内容和项目级最高压缩层的关系，并把判断结果先落回当前话题的 scratch 维护链。

按 scratch 维护模式处理：

| 结果 | 动作 | 写入 |
|:---|:---|:---|
| **无需更新** | 本轮没有影响 Vision / Structure / Style / Trace，只在回复中完成检查判断 | 当前 scratch 记录本轮讨论即可 |
| **候选进 scratch** | 本轮触及目标、结构、风格或追踪链，但仍是讨论胚胎、疑问、临时判断或未稳定变化 | 当前 scratch 标记为 Framework 候选，保留用户原话、判断理由和待确认点 |
| **提出更新方案** | 候选已经稳定、可跨话题复用，并可能改变项目级框架 | 先向用户提出 Framework 更新方案，说明应归入 Vision / Structure / Style / Trace 哪一类 |
| **已获批更新** | 用户确认更新方案后 | 维护 `doc/Framework/` 对应主文件，并在来源 scratch 段落末尾标注 `→ Framework/<类> §<小节>`（如 `→ Framework/Structure §入口与元数据分工`）；同时在 Framework 对应小节补来源索引 `← <话题>/scratch#SNNN` |

Framework 是最高压缩层，不承载试探、临时想法或未审定过程。每轮提醒的意义是防止稳定结论停留在 scratch 里丢失，同时防止未稳定讨论过早写入 Framework。

### ⑥ 双 Git / 源码层判断（项目存在 `.jiacong/source.json` 时）

文件操作前额外判断本轮改动层级：

| 层级 | 典型路径 | 提交纪律 |
|:---|:---|:---|
| 管理层 | `.jiacong/`、`topics/`、`logs/`、`doc/Framework/`、入口文档 | 提交到管理层 Git |
| 内容层 | `source/main/<source_dir>/`、`source/worktrees/`、源码/正文/HTML/产物 | 提交到内容层 Git |
| 混合 | 同一轮同时改管理层与内容层 | 拆提交：先内容层，再管理层记录 |

若项目存在 `.jiacong/source.json`，按其中 `source_root` / `source_dir` 判断内容层位置；若不存在，按当前 cwd 和用户显式路径判断。运行态与生成态默认不提交。

**RUN**

| 场景 | 命令 |
|:---|:---|
| 新建话题 | `python "<skill>/scripts/topic_new.py" <根> <简称> --parent <ID\|null> --root <emoji>` |
| 切焦点 | 写 `.jiacong/focus.json`（旧 `.claude/focus` 仅 fallback mirror）→ `python "<skill>/scripts/focus_breadcrumb.py" <根>` |
| 话题树变更 | `python "<skill>/scripts/tree_gen.py" <根>` |

**REF** → `references/focus-switch.md`（面包屑格式、切换流程、冷启动处理）

---

## §2.1 · 话题

话题是认知的原子单元，一个话题就是 `topics/NNN_简称/` 下的一个扁平目录。这一节讲话题本身的组织规则——什么能往里写、怎么写、怎么命名。

三件套各自的写入规则速查：

| 文件 | 写入方式 | 禁止 |
|:---|:---|:---|
| `scratch.md` | 每轮追加带编号条目，保留回应链 | 删除、清空 |
| `card.md` | 走 `card_write.py` 按 section 融入/替换；结构变更先审批 | 直接追加式堆放、手写改只读目录 |
| `tasks.md` | 任务产生/推进/关闭时更新 | — |

**结构优先于内容**，但有一个例外。如果话题卡已经有了可维护的 TOC，先确定骨架再填正文；新版 card 以 frontmatter `toc:` 为结构源，条目格式为 `"N 标题 | 本节 intent"`，正文标题按 `## N` / `### N.M` 对齐，`📑 本卡目录` 只读渲染。但话题早期往往还没形成 TOC——这时候内容优先：先记录，等内容自然成簇后再给它起个结构名。这叫涌现期（碎片→成簇→骨架），判据见 `references/vision-frameworks.md §0`。不论哪个阶段，写入前都要先识别内容之间的真实承载关系——什么是上层目标、什么是下层路径、什么只是例证——再决定层级，不要把所有东西压平成并列清单。

**内容进话题卡只有两条路：融入或重构。** "融入"是把新内容编入既有章节的论述脉络，让它成为论述的有机部分；常规写入走 `python "<skill>/scripts/card_write.py" <根> <NNN> --section <N> --mode integrate|replace --content-file <path>`，脚本会按 frontmatter toc 校验 section 并输出 intent 语义锚。"重构"是先改 TOC（经用户审批），再把内容迁入新结构；走 `card_write.py --mode restructure --approval pending` 提出，用户批准后再 `--approval approved`。绝不允许在章节末尾追加段落——判别标准很简单：把那段删掉，章节论述还完整吗？完整说明它是追加的（违纪），不完整说明它是融入的。从讨论卡迁入话题卡时，还有一个要求：回应链必须转译为正向建构——不要写"针对前面提到的 X 问题，我们发现 Y"，而要写"Y 是什么、如何运作、为何这样组织"。从对象本身出发，不围绕旧讨论打补丁。

**话题目录平铺在 `topics/` 下**，不嵌套子目录。话题之间通过 `[[NNN_简称]]` 双括号语法关联，通过 frontmatter `parent` 字段表达层级。分组靠 `root` 字段（emoji 标签，如 🎯目标、🧠论证），`tree_gen.py` 按此渲染话题树。

**内容归位**：根目录不放实质内容文件。讨论中的认知进 scratch，提炼后的结论进 card，阶段文档进 `doc/`；项目级最高压缩层进 `doc/Framework/`（Vision / Structure / Style / Trace）。影响目标、完成样态或验收标准的稳定结论回写 Vision；影响目录、模块、对象关系或 codemap 的稳定结论回写 Structure；影响文风、界面手感、表达规则或呈现规范的稳定结论回写 Style；影响任务链、问题链、修复链或决策链的稳定结论回写 Trace。普通讨论仍先留在当前 topic 的 scratch/card/tasks 中，未稳定前不直接写 Framework。思维框架/素材与参考材料（含外部检索线索）/工具/布局进 `base/`（perspectives / resources / tools / disposition）。模板文件中的提示语和占位注释默认是约束，AI 应遵循而非删除。

**`draft/` 人类涂鸦区**：用户自由创建、组织的空间，承载核心理念、灵感碎片、未归类想法。AI 对 `draft/` 的权限为**只读**——可以读取并引用其中内容，但禁止写入、编辑、移动或删除任何文件。`draft/` 中的内容是用户意识与理念的最直接体现，权重高于 card.md 的结论。当 draft 中的想法成熟时，由用户决定是否迁入 topics/ 或 doc/。

**命名语义化**：简称 2-6 字中文或小写英文，≤30 字节，要求一句话能概括话题内容。"新版""改动"这种过于抽象的名字不合格。

**三件套同步维护**：产出独立文件后，必须回填 tasks 的结果/状态、scratch 的讨论记录、card 的索引。独立文件是辐射，三件套是枢纽——下次进来时，从三件套看不到进展，独立文件就成了孤岛。

**RUN**

| 动作 | 命令 |
|:---|:---|
| 新建话题 | `python "<skill>/scripts/topic_new.py" <根> <简称> --parent <ID\|null> --root <emoji> [--with-tasks]` |
| 话题卡写入 | `python "<skill>/scripts/card_write.py" <根> <NNN> --section <N> --mode integrate\|replace --content-file <path>` |
| 结构变更提案 | `python "<skill>/scripts/card_write.py" <根> <NNN> --section <N> --mode restructure --approval pending` |
| 话题卡校验 | `python "<skill>/scripts/check_structure.py" <根> [--card NNN]` |
| 话题树同步 | `python "<skill>/scripts/tree_gen.py" <根>` |

**REF** → `references/topic-lifecycle.md`（三件套 schema、状态流转、原子化判据、迁移流程、命名示范）

---

## §2.2 · 记录机制

项目中有四种记录，各管不同粒度的信息。把它们搞混是常见错误，所以先讲清楚分工。

**scratch** 是最细粒度的记录，每轮对话都写，记的是"当时怎么想的"——讨论过程、推导链、额外文件索引。它活在话题文件夹内部（`topics/NNN/scratch.md`），只关心当前话题。

**log** 是话题级的时间线，记的是"项目经历了什么"——何时开启了一个话题、何时切走、何时关闭。它活在 `logs/stream.md`，覆盖整个项目。log 不是每轮写的，而是在话题开启、切换、关闭这三个节点写。它的读者是"下次冷启动的 AI"，只需要话题级的起承转合，不需要每轮细节。

**Trace（追踪）话题** 是任务导向的记录，记的是"这个问题解决了没"——需求背景、修了什么、为什么改、验收结果。它对应 §3.2 初始化的 Trace 基础话题卡：每个项目初始化时自动建立一张 Trace 卡作为默认追踪枢纽；当某个具体问题需要独立追踪空间时，也可以新建额外的 Trace 话题（root 按 `_seeds.md` 选取，如 `🛠️管理`）。Trace 话题和 log 不矛盾：log 记项目走了哪些话题，Trace 话题记某个具体问题的解决过程。

**Trace 话题 vs tasks.md**：tasks.md 是话题内部的待办清单（"这个话题里还有哪几步没做"），Trace 话题是独立话题（"这个问题需要自己的讨论空间"）。三个触发条件满足任一即开 Trace 话题：①问题需要多轮诊断而非单步执行；②问题跨越多个话题需要协调；③问题需要记录完整的"发现→分析→方案→验证"链条。Trace 话题天然是侧写的汇聚点（见 §1.3 侧写机制），多个话题的进展都可能需要在 Trace 话题上记一笔。

速查对比：

| | scratch | log | tasks.md | Trace 话题 |
|:---|:---|:---|:---|:---|
| **导向** | 过程 | 时间线 | 执行 | 任务 |
| **粒度** | 每轮条目 | 话题级签到/签退 | 话题内待办项 | 需求/bug/修订单 |
| **类比** | git diff | git log --oneline | todo list | issue tracker |
| **读者** | "当时怎么想的" | "项目经历了什么" | "这一步做了没" | "这个问题解决了没" |
| **写入时机** | 每轮回复后 | 话题切换/关闭时 | 任务产生/推进时 | 任务产生/推进/关闭时 |
| **归属** | 话题内部 | 项目级 | 话题内部 | 独立话题 |

### scratch 格式

```
### S001 · [MM-DD HH:MM] 主题

讨论内容...

> 最佳原话>"..."

产出文件：`S001_诊断报告.md`
```

每条 scratch 保留当轮最有价值的一句原话（用户或 AI 的），用 `>` 引用格式。优先保留理念、判断、洞察层面的表达——原话比摘要更能还原语境。

### log 的写入

log 在三个节点写入：话题开启、话题切换、话题关闭。每条 log 不只是一行"开/关"时间戳，而是包含**讨论摘要**和**切换缘由**的结构化条目。

**话题开启时**（包括新建和从其他话题切入）：在 log 预写一条开放条目，标记开始时间和话题。

**话题切换时**：旧话题签退 + 新话题签到。签退时读旧话题的 scratch，汇总成讨论摘要（讨论了什么、形成了什么共识、留下什么遗留问题），并记录切换缘由，补完 log 中旧话题的开放条目。签到时为新话题预写新的开放条目。

**话题关闭时**：读 scratch 生成终结摘要，补完开放条目，标记终态。

log 条目格式：

```
### [MM-DD HH:MM] 签退 NNN_简称
讨论摘要：（从 scratch 汇总，2-5 句）
遗留问题：（如有）
切换缘由：用户主动 / 自然收敛 / 受阻转向 / 无特定缘由
---
### [MM-DD HH:MM] 签到 NNN_简称
```

**RUN** `python "<skill>/scripts/health_check.py" <根> [--json]`（log 超 500 行或 100KB 时提示归档）

---

## §3.1 · 角色

角色解决的问题是：AI 用什么视角思考？通用视角（"我是一个 AI 助手"）什么都能聊但什么都不深。好的角色让 AI 借用顶尖人类的经验、框架和直觉——成为高手的最佳方式是模仿高手、蒸馏高手。

视角应当一以贯之。一旦选定角色，在同一话题域内保持它，不要每轮重选。没有角色也是一种选择——更开放、更普适，但可能更平庸。如果 AI 觉得自己演不好某个角色，应当坦诚说出来，而不是硬撑。

角色必须精确到职能级。不是"方法论学者"，而是"以区域经济为实证场景的方法论学者"。检验句式："你是有 [经验] 的 [角色]，见过 [失败模式]，用 [框架] 思考"——不够具体就补充。每张角色卡包含七个字段：角色名、代表人物群、经验、思考框架、见过的失败、盲区、适用场景。盲区字段尤其重要——一个角色看不到的，由另一个角色补位。

角色库分两层：**项目库**（`<项目根>/base/perspectives/`，仅当前项目用）和**全局库**（`<skill根>/roles-library/`，跨项目共享）。从全局库克隆角色到项目库，用户确认即可。反过来把项目角色升级到全局库，须在 `role_manager.html` 界面显式操作，且需要至少 2 个项目验证过才够资格。

**RUN** `python "<skill>/scripts/role_manager.py" <项目根> [--no-open]` → `.jiacong/dashboard/role_manager.html`

**REF** → `references/roles-ops.md`（选角逻辑、七列说明、双向通道、category 分类）

---

## §3.2 · 初始化

初始化是在新项目中生成脚手架和基础话题卡集。它只在项目不存在时触发（§1.2 会话启动中判断）。

脚手架由**架构套餐**决定，共四套：📄学术论文、📊实证研究、💻代码项目、🛠️短平快。套餐决定目录结构、推荐的 `root` 标签清单（写入 `topics/_seeds.md`）和 `AGENTS.md` 项目入口模板渲染上下文。套餐是建议不是强制，用户可以混合或覆盖，这走结构权（§1.1 总纲）。

除了目录骨架，初始化还会建立一组**基础话题卡**——这些是每类项目开工就需要的结构性话题，各配一个空 doc 作为成型落地区。话题是厨房（讨论和提炼发生的地方），doc 是出菜口（阶段性快照）。

四张基础话题卡跨套餐统一命名，内容随套餐差异化。基础话题卡的 frontmatter 标记 `base_topic: true`，不可删除只可重命名内容。

| 基础话题 | 控制要素 | 学术套餐承载 | 代码套餐承载 |
|:---|:---|:---|:---|
| **Vision** | 方向——做什么、为谁做、做成什么样 | 项目理想样态 + 验收标准 | 产品定位 + 核心能力 |
| **Structure** | 骨架——内容怎么组织 | 论文结构地图 | 以原子化模块为节点，呈现入口、调用、数据流、依赖边界与跨模块勾连的关系地图 |
| **Style** | 表达/呈现——成型对象如何被读到、看到、感到 | 文风控制 + 语言细节（术语、句法、论证节奏、引文/图表表述） | UI 变量的可视层级地图（视觉锚点、状态、交互手感 ↔ 代码变量/组件） |
| **Trace** | 过程——经历了什么、问题解决了没 | 修订快照 + 任务上下文 | changelog + issue 追踪 |

每张基础话题卡各配一个对应的空 doc（如 `doc/vision.md`），作为成型内容的阶段性快照落地区。基础话题卡可选生成第四组件 `template.md`（通过 `--with-template`），用于说明本话题如何写、重复单元如何实例化、地图型对象如何渲染；它约束 `card.md` 的写入方式，但不替代 `card.md` 的结论源地位。

初始化前先和用户确认验收判据；稳定后写入 `doc/Framework/Vision/Vision.md`，项目入口 `AGENTS.md` 只保留权威指针。标准骨架选型（PRD / User Story / IMRaD 等）见 `references/vision-frameworks.md §2`。如果目录里有旧版结构，脚本会报告迁移建议，但不自动改动——经用户确认后才执行。

入口先按 `references/init-project.md §1.5` 判定文件夹角色：既有 `.git` 项目默认原位建档；外层 workspace 容器只承载 `.repo.git`、`main/`、`worktrees/` 与 `.jiacong-workspace/current-worktree`，不承载 `topics/` 或 `logs/`；多 repo、混合 `.git/.repo.git`、半建档痕迹先停止自动初始化并确认迁移策略。

**RUN** `python "<skill>/scripts/init_project.py" <根> --type <学术|实证|代码|短平快>`

若用户希望采用当前推荐的“外层 workspace 容器 + 内层 main/worktrees 项目根”模式，使用：

**RUN** `python "<skill>/scripts/init_project.py" <workspace根> --type <学术|实证|代码|短平快> --workspace`

workspace 模式会在外层创建 `.repo.git/`、`main/`、`worktrees/`、`.jiacong-workspace/current-worktree` 和多 CLI 容器入口；真正的 smarter-project 建档文件写入 `main/`。Claude、Codex、Gemini 都应先解析外层 active project root，再进入内层项目根读取 `AGENTS.md`、`CLAUDE.md`、`GEMINI.md`。

**源码子仓库（--source-dir）**：workspace 模式下，`--source-dir` 指定源码所在的子目录名（默认 `app`）。设为 `--source-dir .` 表示项目根即源码根，跳过子仓库初始化。详见 `references/init-project.md §1.5`。

多 CLI hook 映射：Claude/Codex 使用原事件名；Gemini 使用原生 `BeforeAgent` 承接 UserPromptSubmit 上下文注入、`AfterTool` 承接 PostToolUse 文件触达记录、`AfterAgent` 承接 Stop 纪律阻断。

若当前目录只有历史文件、没有 `.git`、也没有 `.claude/topics/logs` 建档痕迹，可加 `--adopt-existing`，脚本会把外层已有文件移动进 `main/` 后再完成 `main/` 建档。默认不移动历史文件；遇到 `.git` 或已建档项目根时停止，避免破坏既有仓库或双重建档。

分支完成后使用 `python app/workspace_use.py --workspace <workspace根> archive <branch>` 归档非 active worktree：脚本会要求 worktree 干净，写 `.jiacong-workspace/archive/branches/<branch>/<timestamp>/` 快照和 metadata，创建 `archive/<branch>/<timestamp>` tag，然后移除 worktree 并默认删除本地 branch；恢复命令记录在 metadata 的 `restore` 字段。

产物：`AGENTS.md` canonical 入口 + `CLAUDE.md` / `GEMINI.md` / `HERMES.md` adapter + `.jiacong/project.json` / `.jiacong/entrypoints.json` + `topics/_seeds.md` + `topics/_tree.md` + `logs/stream.md` + `doc/Framework/` + 基础 Framework 文件 + 套餐特定目录。`.claude/CLAUDE.md` 仅保留既有旧项目 fallback，不默认生成。

**REF** → `references/init-project.md`（套餐详情、三层目录原则）· `references/vision-frameworks.md`（产品原型骨架选型）· `references/base-topic-templates.md`（基础话题 template.md、单元模板与地图渲染）

---

## §4 · 审查

审查是按需触发的结构一致性检查。之所以不自动全扫，是因为审查有 token 成本，按需比例行经济。

**结构审查** 检查话题卡的 TOC 与正文是否对齐、链接是否有效。发现问题后，AI 提议重整方案，经用户审批后只搬移章节位置，不重新生成正文——重摆前后内容字节数基本不变。

**反向审查** 锚定在 **Vision 基础话题卡**（§3.2 初始化）上。当 Vision 卡的方向、目标或验收标准发生变更后，检查已有话题卡的结论是否仍然成立。三个判据：结论与 Vision 矛盾？Vision 不再支持本卡推论链？Vision 新概念应在本卡体现却未体现？任一命中即提示用户。**Structure 卡**变更时做同样检查——骨架调整可能导致已有话题卡的章节归位失效。

**RUN**

| 动作 | 命令 |
|:---|:---|
| 结构审查 | `python "<skill>/scripts/check_structure.py" <根> [--card NNN]` |
| 单元校验 | `python "<skill>/scripts/check_units.py" <根> [--card NNN]` |
| 地图渲染 | `python "<skill>/scripts/render_maps.py" <根> [--card NNN]` |
| 断链审查 | `python "<skill>/scripts/check_links.py" <根>` |
| 反向审查 | 手动按 `references/review-ops.md §2` 流程 |

**REF** → `references/review-ops.md`（反向审查触发模式、结构审查流程、重摆纪律）

---

## 附录 · 脚本速查

| 脚本 | 命令 |
|:---|:---|
| `init_project.py` | `python "<skill>/scripts/init_project.py" <根> --type <学术\|实证\|代码\|短平快>` |
| `init_project.py --workspace` | `python "<skill>/scripts/init_project.py" <workspace根> --type <学术\|实证\|代码\|短平快> --workspace` |
| `init_project.py --workspace --adopt-existing` | `python "<skill>/scripts/init_project.py" <workspace根> --type <学术\|实证\|代码\|短平快> --workspace --adopt-existing` |
| `init_project.py --workspace --source-dir` | `python "<skill>/scripts/init_project.py" <workspace根> --type <学术\|实证\|代码\|短平快> --workspace --source-dir <app\|src\|.\>` |
| `topic_new.py` | `python "<skill>/scripts/topic_new.py" <根> <简称> --parent <ID\|null> --root <emoji>` |
| `tree_gen.py` | `python "<skill>/scripts/tree_gen.py" <根>` |
| `active_topics.py` | `python "<skill>/scripts/active_topics.py" <根> [--days N --limit N --json]` |
| `focus_breadcrumb.py` | `python "<skill>/scripts/focus_breadcrumb.py" <根>` |
| `health_check.py` | `python "<skill>/scripts/health_check.py" <根> [--json]` |
| `dashboard.py` | `python "<skill>/scripts/dashboard.py" <根>` |
| `check_links.py` | `python "<skill>/scripts/check_links.py" <根> [--json]` |
| `check_structure.py` | `python "<skill>/scripts/check_structure.py" <根> [--card NNN --json]` |
| `check_units.py` | `python "<skill>/scripts/check_units.py" <根> [--card NNN --json]` |
| `render_maps.py` | `python "<skill>/scripts/render_maps.py" <根> [--card NNN]` |
| `role_manager.py` | `python "<skill>/scripts/role_manager.py" <根> [--no-open]` |
| `card_write.py` | `python "<skill>/scripts/card_write.py" <根> <NNN> --section <N> --mode integrate\|replace --content-file <path>` |
| `watcher.py` | `python "<skill>/scripts/watcher.py" <根>`（后台守护进程，监视 topics/ 变更并触发增量更新；由 session_start hook 启动） |
| `flow_hook.py` | `python "<skill>/scripts/flow_hook.py"（PostToolUse hook 回调，检测 Edit/Write 对 card.md/scratch.md 的直接修改，warn 级提醒 + autofix）` |

共用库：`scripts/_lib/topics_loader.py::load_topics(root)` · `scripts/_lib/flow.py` · `scripts/_lib/common.py`（套餐定义、模板渲染、通用工具函数） · `scripts/_lib/structure.py`（card 结构解析：frontmatter toc + 正文标题比对） · `scripts/_lib/autofix.py`（幂等自动修复：frontmatter 补字段、scratch 状态修正）

环境：Python 3.10+；`pip install -r requirements.txt`（jinja2 + python-frontmatter）。
