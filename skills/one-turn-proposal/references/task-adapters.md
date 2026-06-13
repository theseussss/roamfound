# Task Adapters

Use these adapters to specialize the core protocol. Do not load every adapter into the answer. Choose the closest one and blend it naturally with the user's request.

## 1. Framework design adapter

Use when the user is designing a framework, methodology, protocol, taxonomy, operating model, or reusable standard.

Judgment question:

```text
should this be a principle, core module, optional module, hidden mechanism, or scenario-specific adapter?
```

Recommended structure:

```text
需求理解
核心判断
设计原则
总体架构
模块归位
使用流程
反模式 / 不纳入项
示例用法
下一步
```

What to include:

- what belongs in the core
- what belongs in optional adapters
- what should stay hidden or internal
- what should be excluded to avoid bloat
- how existing frameworks map to operational roles when methodology provenance matters
- evaluation criteria if the framework is meant to become a reusable system
- naming and versioning if the framework is reusable

Common mistakes:

- turning the framework into a rigid checklist
- adding too many theories without assigning operational roles
- failing to define when the framework should not be used

## 2. Strategy / business adapter

Use for market, company, GTM, positioning, operating model, or growth strategy.

Judgment question:

```text
what is the highest-leverage strategic choice, and what should be deprioritized?
```

Recommended structure:

```text
现状判断
核心问题
战略选择
推荐路径
关键举措
资源与节奏
风险与反证
下一步决策
```

What to include:

- explicit strategic trade-off
- who the strategy serves
- what not to do
- time horizon
- success indicators

Common mistakes:

- listing generic initiatives
- avoiding prioritization
- treating all options as equally good

## 3. Product adapter

Use for product ideas, user needs, feature design, MVP, roadmap, or product requirements.

Judgment question:

```text
what user problem should be solved first, and what is the smallest valuable product shape?
```

Recommended structure:

```text
目标用户
用户痛点
核心价值主张
产品方案
MVP 范围
关键流程 / 信息架构
成功指标
风险与不做事项
下一步验证
```

Use PR-FAQ style when the user is exploring a new product concept:

```text
future press release angle
customer problem
why now
customer benefit
faq / objections
```

Use PRD style when the user needs implementation detail:

```text
goals
non-goals
user stories
requirements
metrics
launch plan
open questions
```

Common mistakes:

- jumping to features before defining the user problem
- making the MVP too large
- omitting non-goals

## 4. Technical / architecture adapter

Use for system design, engineering architecture, API design, data flow, implementation choice, or migration plan.

Judgment question:

```text
which architecture or implementation path best satisfies the constraints, and what trade-offs are accepted?
```

Recommended structure:

```text
背景与目标
约束条件
备选方案
推荐方案
架构 / 流程
实施步骤
风险、回滚与监控
未决问题
```

Use RFC style when proposing a technical design. Use ADR style when recording a decision among alternatives.

Common mistakes:

- giving code before clarifying constraints
- failing to mention rollback, migration, or observability
- ignoring rejected alternatives

## 5. Decision support adapter

Use when the user is choosing between options or asks "should I" / "which is better".

Judgment question:

```text
under the user's likely priorities, which option should be chosen now?
```

Recommended structure:

```text
决策问题
我的建议
判断依据
备选项比较
选择后果
何时重新评估
下一步动作
```

Rules:

- Give a recommendation unless there is truly not enough information.
- Identify the dominant criterion.
- State what information would change the recommendation.

Common mistakes:

- giving a pros/cons table without deciding
- asking for more information when a provisional recommendation is possible

## 6. Writing / communication adapter

Use for drafting, rewriting, messaging, storytelling, speech, emails, posts, essays, or proposals.

Judgment question:

```text
what should this piece make the audience think, feel, or do?
```

Recommended structure:

```text
意图理解
表达策略
成稿 / 改写稿
为什么这样写
可调整方向
```

Rules:

- Usually produce the actual draft, not only advice.
- Preserve the user's intent but improve structure, tone, and clarity.
- Offer one or two alternative tones when useful.

Common mistakes:

- explaining writing principles instead of writing
- over-polishing until the user's voice disappears

## 7. Research / synthesis adapter

Use for literature review, market scan, policy summary, trend analysis, source synthesis, or complex factual questions.

Judgment question:

```text
what is the best-supported synthesis, and how certain is it?
```

Recommended structure:

```text
问题定义
结论先行
证据结构
主要分歧 / 不确定性
综合判断
后续验证
```

Rules:

- Use external sources and citations when required by system instructions or when facts may be current or niche.
- Consult `evidence-retrieval-protocol.md` when deciding search depth and source types.
- Consult `source-critical-appraisal.md` when source quality affects the conclusion.
- Consult `search-completeness-awareness.md` when the answer might otherwise imply false completeness.
- Separate evidence from inference.
- State uncertainty clearly.
- For formal research answers, include a concise search note: source types, scope, inclusion/exclusion logic, and completeness boundary.

Common mistakes:

- summarizing sources without synthesizing
- treating uncertain findings as settled
- citing sources without appraising reliability
- claiming comprehensive coverage from a shallow search

## 8. Review / critique adapter

Use when the user asks for feedback on a document, idea, framework, design, code, pitch, or plan.

Judgment question:

```text
what is working, what is not, and what change would most improve it?
```

Recommended structure:

```text
总体判断
亮点
主要问题
优先修改建议
可直接替换的版本 / 示例
风险与下一步
```

Rules:

- Start with a clear overall evaluation.
- Prioritize issues by impact.
- Include concrete fixes, not only critique.

Common mistakes:

- giving equal-weight comments
- being polite but not useful
- failing to show a revised version when a rewrite is possible

## 9. Execution / project planning adapter

Use for implementation plans, rollout plans, checklists, operating rhythms, team workflows, or roadmaps.

Judgment question:

```text
what sequence reduces risk fastest while creating visible progress?
```

Recommended structure:

```text
目标
阶段划分
每阶段产出
责任 / 资源
风险与依赖
验收标准
下一步启动项
```

Rules:

- Define concrete outputs for each phase.
- Identify the first irreversible or high-risk step.
- Include success criteria.

Common mistakes:

- giving a timeline without outputs
- ignoring dependencies

## 10. Methodology audit adapter

Use when the user asks whether the protocol is coherent, whether frameworks are correctly integrated, whether there is semantic loss, or how to evolve the framework as a methodology system.

Judgment question:

```text
which parts are core method, which are optional adapters, which are hidden mechanisms, and which should be excluded to preserve usability?
```

Recommended structure:

```text
总体判断
方法论定位
框架归位图
语义保留 / 语义压缩 / 语义丢失
需要补强的模块
不建议纳入的内容
下一版演进路径
```

What to include:

- whether the system is a template, protocol, skill, product feature, or methodology
- mapping of source frameworks to operational roles
- where semantic compression is intentional
- where true semantic loss exists
- the smallest set of changes needed for the next version
- evaluation criteria or test cases when relevant

Common mistakes:

- defending the system without audit
- saying "no semantic loss" without showing the mapping
- adding frameworks because they sound sophisticated
- confusing visible output sections with hidden operating mechanisms
