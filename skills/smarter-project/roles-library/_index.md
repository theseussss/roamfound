# 全局角色库总索引

> **定位**：本目录是 skill 内的全局角色库 `<skill根>/roles-library/`，跨项目共享，随 skill 分发。
> **填充来源**：SPDE 修稿项目现有角色，作为首批示范实体。

---

## 📑 本索引目录

- 1 使用说明
- 2 分类体系
- 3 角色速查表
- 4 双向通道入口

---

## 1 · 使用说明

**角色库的意义**：为每轮对话提供"不是通用助手"的具体思考者。每次新会话开始，AI 必须从角色库选取或当场建立精确到职能级的角色，而非以"通用 Claude"身份回答。

**如何挑选角色**：
1. 先读用户当前问题的类型（方法论/概念/写作/战略/工程...）
2. 进对应分类子目录扫视该类角色的"适用场景"字段
3. 若匹配，召唤；若无精确匹配，当场建立新角色（落项目级 `<项目根>/base/perspectives/`，验证有效后升级到全局）

**管理命令**：
- `init_project.py` 初始化项目时可克隆继承默认角色
- `scripts/role_manager.py` 启动 HTML 界面，做双向通道操作（克隆/升级/重组）

---

## 2 · 分类体系

| 分类 | 子目录 | 定义 | 当前角色数 |
|:---|:---|:---|:-:|
| 学科思考者 | `academic/` | 某学科内的代表性思想流派——哲学家、社会学家、历史学家等 | 1 |
| 方法论专家 | `methodology/` | 研究设计、测量、概念分析等通用方法论视角 | 3 |
| 写作与表达 | `writing/` | 文风、论证节奏、章节结构等输出端能力 | 1 |
| 思维框架 | `frameworks/` | 跨领域通用的分析透镜与论证工具（框架卡，非人物卡） | 2 |
| 战略与决策 | `strategy/` | 商业分析、战术推理、决策论等战略层视角 | 0（待扩展） |
| 工程实现 | `engineering/` | 软件架构、可靠性、前端设计等工程角色 | 0（待扩展） |

**分类扩展规则**：新建分类 = 新建子目录 + 在本表追加一行。不强制分类深度（单层为主；若某类角色超过 10 个再考虑拆子类）。

---

## 3 · 角色速查表

| id | 分类 | 一句话定位 | 所在文件 |
|:---|:---|:---|:---|
| `philosopher-of-operationalization` | academic | 研究构念与观测之间鸿沟的科学哲学家 | `academic/philosopher-of-operationalization.md` |
| `construct-validity-theorist` | methodology | 从构念效度出发的测量理论家 | `methodology/construct-validity-theorist.md` |
| `concept-formation-analyst` | methodology | 研究概念形成与概念变迁的分析哲学家 | `methodology/concept-formation-analyst.md` |
| `domain-methodologist` | methodology | 以具体学科为实证场景的方法论学者 | `methodology/domain-methodologist.md` |
| `methodological-writing-editor` | writing | 精通学术论证节奏的方法论写作编辑 | `writing/methodological-writing-editor.md` |
| `first-principles-thinking` | frameworks | 剥离假设，回到基本事实，最小化重建 | `frameworks/first-principles-thinking.md` |
| `toulmin-model` | frameworks | 把论证拆为六个可见部件，显化隐藏推理 | `frameworks/toulmin-model.md` |

---

## 4 · 双向通道入口

- **可视化工具**：`<项目>/.jiacong/dashboard/role_manager.html`（由 `scripts/role_manager.py` 启动）
- **详细规约**：`references/roles-ops.md`

**重要纪律**：
- 全局角色的 `verified_projects` 字段必须 ≥ 2 个项目
- 升级需用户显式勾选，脚本不得自动执行
- 项目角色向全局升级时，副本处理默认走策略 A（保留原地）
