# smarter-project skill v2 · 目录架构（示范文档）

> 建立：2026-04-19
> 最后更新：2026-05-12
> 原则：**一级按类型 → 二级按功能域 → 三级按细节**
> 类型定义：scripts=可执行代码 | templates=Jinja2可渲染模板 | references=AI必读规约 | roles-library=skill内全局角色库
>
> 本文是示范性架构说明，用于对接理解；运行时真理源是 SKILL.md 与 references/。

---

## 一、完整目录树

```
smarter-project/
│
├── SKILL.md                         ← 唯一入口：按执行流组织
│                                       §1.1 总纲 · §1.2 会话启动 · §1.3 每轮循环
│                                       §2.1 话题 · §2.2 记录机制 · §3.1 角色
│                                       §3.2 初始化 · §4 审查
│                                       附录：脚本速查
│
├── ALGORITHM.md                     ← 算法框架（SKILL.md 重写的设计依据）
├── ARCHITECTURE.md                  ← 本文（示范文档）
│
│
│   ══════════════════════════════════════════════════════════════
│   类型一：scripts/  ── 可执行 Python 脚本
│   判定：文件是 .py，被 python 解释器执行
│   ══════════════════════════════════════════════════════════════
│
├── scripts/
│   │
│   ├── _lib/                        ── 共享库（被所有脚本 import，不独立执行）
│   │   ├── __init__.py                 包标识
│   │   ├── autofix.py                  card.md / scratch.md 的确定性自动修复器
│   │   ├── common.py                   UTF-8配置 / 路径校验 / 时间戳 / 架构套餐数据
│   │   ├── flow.py                     话题流转事件日志（append-only → flow-log.jsonl）
│   │   ├── structure.py                card.md TOC / 正文结构校验公共逻辑
│   │   └── topics_loader.py            话题 md 解析 / mtime 缓存 / TOC 提取
│   │
│   │   ┌─ topic 域 ─────────────────────────────────────────┐
│   ├── topic_new.py                    新建话题三件套（scratch+card+tasks）
│   ├── tree_gen.py                     话题树生成（mermaid + ASCII 双轨）
│   ├── active_topics.py                活跃话题列表（按 mtime 降序）
│   ├── card_write.py                   card.md 结构化写入通道
│   ├── render_maps.py                  从 card.md 单元生成地图辅助视图
│   │   └─────────────────────────────────────────────────────┘
│   │
│   │   ┌─ project 域 ───────────────────────────────────────┐
│   ├── init_project.py                 按套餐初始化项目脚手架（AGENTS.md 渲染 project_entry.md.tmpl，adapter 指向 AGENTS.md）
│   ├── focus_breadcrumb.py             焦点面包屑渲染
│   ├── dashboard.py                    汇总生成 .jiacong/dashboard/index.html
│   ├── watcher.py                      项目状态守护进程（监听变更 + 防抖刷新派生视图）
│   │   └─────────────────────────────────────────────────────┘
│   │
│   │   ┌─ monitor 域 ──────────────────────────────────────┐
│   ├── health_check.py                 健康检查（stream/vision/card/links/status）
│   ├── check_links.py                  [[NNN_简称]] 校验
│   ├── check_structure.py              TOC/正文对齐校验
│   ├── check_units.py                  template.md 单元模板校验
│   │   └─────────────────────────────────────────────────────┘
│   │
│   │   ┌─ hook 域 ─────────────────────────────────────────┐
│   ├── flow_hook.py                    PostToolUse hook（plugin 安装即启用）
│   │   └─────────────────────────────────────────────────────┘
│   │
│   │   ┌─ role 域 ─────────────────────────────────────────┐
│   └── role_manager.py                 角色管理 HTML 生成 + 浏览器打开
│       └─────────────────────────────────────────────────────┘
│
│       注：scripts/ 保持扁平不建子目录。原因：
│       ① 15 个脚本子目录化不增可读性；
│       ② dashboard.py 用 importlib 按文件名动态加载同级脚本；
│       ③ 域归属通过上方注释标明，>20 个再考虑子目录。
│
│
│   ══════════════════════════════════════════════════════════════
│   类型二：templates/  ── Jinja2 可渲染模板
│   判定：文件后缀 .tmpl，含 {{ 变量 }}，被脚本读取后渲染输出
│   ══════════════════════════════════════════════════════════════
│
├── templates/
│   │
│   ├── console.html.tmpl            ── 根级：控制台页面      → flow_hook.py / dashboard.py
│   │
│   ├── topic/                       ── 功能域：话题三件套 + 话题树 + 单元模板
│   │   ├── card.md.tmpl                话题卡         → topic_new.py / init_project.py
│   │   ├── scratch.md.tmpl             讨论卡         → topic_new.py / init_project.py
│   │   ├── tasks.md.tmpl               任务卡         → topic_new.py --with-tasks
│   │   ├── template.md.tmpl            单元模板       → init_project.py（基础话题第四组件）
│   │   └── _tree.md.tmpl               话题树         → tree_gen.py
│   │
│   ├── role/                        ── 功能域：角色
│   │   ├── profile.md.tmpl             角色卡（7 栏）  → 新建角色时渲染
│   │   └── manager.html.tmpl           角色管理器页面 → role_manager.py
│   │
│   └── project/                     ── 功能域：项目级
│       ├── project_entry.md.tmpl        AGENTS.md 项目入口正文模板 → entrypoints.py / init_project.py
│       └── dashboard.html.tmpl         仪表盘页面     → dashboard.py
│
│       注：templates/ 内每个文件必须是 .tmpl 后缀。
│       如果一个 .md 不含 {{ }} 变量、不被脚本渲染，它不属于这里。
│
│
│   ══════════════════════════════════════════════════════════════
│   类型三：references/  ── AI 必读的规约文档
│   判定：.md 文件，内容是规范/规约/操作手册，SKILL.md 路由 AI 来读
│   ══════════════════════════════════════════════════════════════
│
├── references/
│   │
│   ├── base-topic-templates.md      基础话题模板与第四组件机制                 锚定 §3.2
│   ├── init-project.md              新项目初始化 / 选套餐 / 脚手架生成        锚定 §3.2
│   ├── topic-lifecycle.md           话题全生命周期（新建/讨论/沉淀/收敛/派生） 锚定 §2.1
│   ├── focus-switch.md              焦点切换 / 面包屑 / 未完成焦点警告        锚定 §1.3
│   ├── roles-ops.md                 角色管理 / 双向通道 / 审批门              锚定 §3.1
│   ├── review-ops.md                反向审查 / 结构审查 / 脚本告警处理        锚定 §4
│   ├── vision-frameworks.md         产品原型文档骨架参考（五骨架选型）         锚定 §3.2
│   └── proposal-bridge.md           并列 one-turn-proposal skill 桥接规则      锚定 §1.3
│
│       注：references/ 保持扁平（8 个文件），skill-creator 规范要求一层为限。
│       每个文件开头必带"锚定 SKILL.md §N"一行，
│       形成"下钻带锚"的环扣——AI 在 reference 里不走丢。
│
│
│   ══════════════════════════════════════════════════════════════
│   类型四：roles-library/  ── skill 内全局角色库
│   判定：.md 内容文件，跨项目共享的角色种子，随 skill 分发
│   ══════════════════════════════════════════════════════════════
│
├── roles-library/
│   │
│   ├── _index.md                    总索引：分类体系 + 使用说明 + 速查表
│   │
│   ├── academic/                    ── 学科思考者
│   │   └── philosopher-of-operationalization.md
│   │
│   ├── methodology/                 ── 方法论专家
│   │   ├── concept-formation-analyst.md
│   │   ├── construct-validity-theorist.md
│   │   └── domain-methodologist.md
│   │
│   └── writing/                     ── 写作与表达
│       └── methodological-writing-editor.md
│
│       注：roles-library/ 与 references/ 的区别——
│       references/ 是"AI 读了之后知道怎么做"的操作手册；
│       roles-library/ 是"被 role_manager.py 扫描并可克隆到项目 base/perspectives/"的实体内容。
│       角色卡(.md)是内容数据，不是给 AI 读的规范。
│
│
│   ══════════════════════════════════════════════════════════════
│   类型五：docs/  ── 示例配置文件
│   判定：非代码、非模板、非规约的辅助文档/示例
│   ══════════════════════════════════════════════════════════════
│
├── docs/
│   └── settings-hook-example.json   flow-log PostToolUse hook 配置示例
│
│
│   ══════════════════════════════════════════════════════════════
│   其他
│   ══════════════════════════════════════════════════════════════
│
└── _smoke*/                         冒烟测试产物（不参与正式流程，可随时重建）
```

---

## 二、自检：类型一致性验证

### scripts/ 自检

| 文件 | 是 .py？ | 调用方式 | ✓ |
|:---|:-:|:---|:-:|
| `_lib/__init__.py` | ✓ | import | ✓ |
| `_lib/autofix.py` | ✓ | import | ✓ |
| `_lib/common.py` | ✓ | import | ✓ |
| `_lib/flow.py` | ✓ | import | ✓ |
| `_lib/structure.py` | ✓ | import | ✓ |
| `_lib/topics_loader.py` | ✓ | import | ✓ |
| `init_project.py` | ✓ | `python init_project.py <root> --type 学术` | ✓ |
| `topic_new.py` | ✓ | `python topic_new.py <root> <简称>` | ✓ |
| `tree_gen.py` | ✓ | `python tree_gen.py <root>` | ✓ |
| `active_topics.py` | ✓ | standalone / dashboard.py import | ✓ |
| `card_write.py` | ✓ | `python card_write.py <root> <话题>` | ✓ |
| `render_maps.py` | ✓ | `python render_maps.py <root> <话题>` | ✓ |
| `focus_breadcrumb.py` | ✓ | standalone / dashboard.py import | ✓ |
| `dashboard.py` | ✓ | `python dashboard.py <root>` | ✓ |
| `watcher.py` | ✓ | `python watcher.py <root>` | ✓ |
| `health_check.py` | ✓ | standalone / dashboard.py import | ✓ |
| `check_links.py` | ✓ | `python check_links.py <root>` | ✓ |
| `check_structure.py` | ✓ | `python check_structure.py <root>` | ✓ |
| `check_units.py` | ✓ | `python check_units.py <root>` | ✓ |
| `flow_hook.py` | ✓ | PostToolUse hook 自动调用 | ✓ |
| `role_manager.py` | ✓ | `python role_manager.py <root>` | ✓ |

**结论**：21 个 .py 文件，无异类。✓

### templates/ 自检

| 文件 | .tmpl？ | 含 {{ }}？ | 渲染者 | ✓ |
|:---|:-:|:-:|:---|:-:|
| `console.html.tmpl` | ✓ | ✓ | flow_hook, dashboard | ✓ |
| `topic/card.md.tmpl` | ✓ | ✓ | topic_new, init_project | ✓ |
| `topic/scratch.md.tmpl` | ✓ | ✓ | topic_new, init_project | ✓ |
| `topic/tasks.md.tmpl` | ✓ | ✓ | topic_new | ✓ |
| `topic/template.md.tmpl` | ✓ | ✓ | init_project | ✓ |
| `topic/_tree.md.tmpl` | ✓ | ✓ | tree_gen | ✓ |
| `role/profile.md.tmpl` | ✓ | ✓ | 角色新建流程 | ✓ |
| `role/manager.html.tmpl` | ✓ | ✓ | role_manager | ✓ |
| `project/project_entry.md.tmpl` | ✓ | ✓ | init_project | ✓ |
| `project/dashboard.html.tmpl` | ✓ | ✓ | dashboard | ✓ |

**结论**：10 个 .tmpl 文件，无异类。✓

### references/ 自检

| 文件 | 规约性质 | 锚定 SKILL.md | ✓ |
|:---|:---|:---|:-:|
| `base-topic-templates.md` | 基础话题模板与第四组件机制 | §3.2 初始化 | ✓ |
| `init-project.md` | 初始化操作手册 | §3.2 初始化 | ✓ |
| `topic-lifecycle.md` | 三位一体状态流全判据 | §2.1 话题（§1.1 结构权 · §2.2 记录） | ✓ |
| `focus-switch.md` | 焦点切换规则 + 警告文案 | §1.3 每轮循环（§1.1 结构权） | ✓ |
| `roles-ops.md` | 角色分类 + 双向通道 | §3.1 角色 | ✓ |
| `review-ops.md` | 反向审查 + 结构审查 | §4 审查（§2.1 话题 TOC） | ✓ |
| `vision-frameworks.md` | 产品原型文档骨架参考 | §3.2 初始化（§2.1 · §1.1） | ✓ |
| `proposal-bridge.md` | 并列 one-turn-proposal skill 桥接规则 | §1.3 执行回复 | ✓ |

**结论**：8 个 .md 规约，无内容数据混入。✓

### roles-library/ 自检

| 文件 | 内容性质 | 被谁使用 | ✓ |
|:---|:---|:---|:-:|
| `_index.md` | 索引 | role_manager.py 扫描 | ✓ |
| `academic/philosopher-of-operationalization.md` | 角色卡 | 克隆到项目 base/perspectives/ | ✓ |
| `methodology/concept-formation-analyst.md` | 角色卡 | 同上 | ✓ |
| `methodology/construct-validity-theorist.md` | 角色卡 | 同上 | ✓ |
| `methodology/domain-methodologist.md` | 角色卡 | 同上 | ✓ |
| `writing/methodological-writing-editor.md` | 角色卡 | 同上 | ✓ |

**结论**：6 个内容文件，无规约/模板混入。✓

---

## 三、五种类型各有一个动词

| 类型 | 动词 | 谁用 | 生命周期 |
|:---|:---|:---|:---|
| scripts/ | **执行** (run) | Python 解释器 | 随 skill 版本 |
| templates/ | **渲染** (render) | 脚本读取并 Jinja2 渲染 | 随 skill 版本 |
| references/ | **阅读** (read) | AI 在触发场景下必读 | 随 skill 版本 |
| roles-library/ | **克隆** (clone) | role_manager.py 复制到 `<项目根>/base/perspectives/` | 跨项目共享，项目副本可独立演化 |
| docs/ | **参考** (refer) | 用户手动合并到配置中 | 随 skill 版本 |

**roles-library/ 为何独立**：
- 与 references/ 性质不同——不是"读规范"而是"克隆实体内容"
- 跨项目沉淀的角色需要全局稳定位置，不能每项目一份副本
- 升级（项目→全局）走 role_manager.py 审批门，脚本不自动

---

## 四、文件计数汇总

| 类型 | 文件数 | 子目录数 |
|:---|:-:|:-:|
| SKILL.md（根） | 1 | — |
| ALGORITHM.md（根，算法框架） | 1 | — |
| ARCHITECTURE.md（根，示范） | 1 | — |
| scripts/ | 21 (.py) | 1 (_lib/) |
| templates/ | 10 (.tmpl) | 3 (topic/ role/ project/) |
| references/ | 8 (.md) | 0 |
| roles-library/ | 6 (.md) | 3 (academic/ methodology/ writing/) |
| docs/ | 1 (.json) | 0 |
| **合计** | **49** | **7** |
