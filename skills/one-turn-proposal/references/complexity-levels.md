# Complexity Levels

Use this file to decide how much structure the answer needs. The skill should feel adaptive, not templated.

## Level 1: direct answer

Use when:

- the user asks for a quick fact, rewrite, definition, micro-decision, or narrow suggestion
- the request has low ambiguity and low consequence
- a formal structure would create friction

Visible shape:

```text
答案 / 改写 / 建议
简短理由
可选下一步
```

Rules:

- Do not restate the whole request unless it prevents misunderstanding.
- Do not use proposal headings.
- Do not add risk sections unless risk is material.

Example:

```text
建议用“回答协议”，不要用“回答模板”。“协议”更强调行为规则和动态适配，“模板”容易让人联想到固定格式。
```

## Level 2: standard structured answer

Use when:

- the user asks for advice, analysis, planning, critique, framework comparison, or a thoughtful answer
- the request is moderately ambiguous but answerable with assumptions
- the user would benefit from a clear judgment and next step

Default visible shape:

```text
我理解你的需求是……
我的判断是……
可以拆成……
我建议……
需要注意……
下一步……
```

Rules:

- Restate the need briefly and insightfully.
- Make a judgment within the first third of the answer.
- Use sections only where they add clarity.
- End with one next step or a small set of options.

## Level 3: formal proposal

Use when:

- the user asks for a deliverable, architecture, Skill, framework, strategy, PRD, RFC, decision memo, research brief, or formal plan
- the request affects multiple stakeholders or implementation steps
- the answer should be reusable outside the conversation
- the user explicitly asks for "可交付", "正式", "架构", "方案", "提案", "分文件", "框架", or similar language

Default visible shape:

```text
1. 需求理解
2. 核心判断
3. 设计原则
4. 总体架构
5. 模块设计
6. 使用流程
7. 风险与边界
8. 交付物 / 下一步
```

Rules:

- Produce an artifact or artifact-ready structure when possible.
- Include implementation details, not only concepts.
- Be explicit about what is included and what is intentionally excluded.
- Use task-specific templates from `response-templates.md` when useful.

## Escalators

Move to a higher level when the request includes:

- "正式", "可交付", "产品化", "架构", "提案", "系统", "规范", "落地", "路线图"
- multiple frameworks or options that need consolidation
- strategic, product, technical, legal, financial, medical, or organizational consequences
- need for reusable output across future conversations or teams

## De-escalators

Move to a lower level when:

- the user asks for a quick answer or small edit
- the answer is obvious and low-risk
- the user is in the middle of iterative drafting and only needs the next revision
- a full structure would slow the interaction down

## Default choice

When unsure, choose Level 2. If the user asks for a deliverable or artifact, choose Level 3. If the user asks for a quick edit or direct answer, choose Level 1.
