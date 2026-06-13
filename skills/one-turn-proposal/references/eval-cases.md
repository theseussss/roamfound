# Evaluation Cases

Use this file to test whether the skill behaves like a methodology-backed dynamic protocol rather than a rigid template. These cases are for improving the skill, not for normal user-facing answers.

## Scoring rubric

Score each answer from 0 to 2 on each criterion.

| Criterion | 0 | 1 | 2 |
|---|---|---|---|
| need reconstruction | repeats prompt or misses intent | partially reframes | identifies real goal and success condition |
| judgment | no position | weak or delayed position | clear early recommendation, priority, or rejection |
| structure fit | too flat or too heavy | usable but uneven | matches complexity level and task |
| proposal quality | advice only | partial path | concrete proposal or artifact-ready structure |
| execution | no next action | generic next action | specific step, test, checklist, or deliverable |
| risk and boundary | none | generic caveat | material assumptions, limits, or trade-offs |
| interaction | many weak questions or none | okay continuation | one strong next step or small useful choice set |
| anti-bloat | theory/template dumping | some unnecessary sections | concise and adaptive |

Target score:

- Level 1: at least 10 / 16, with low bloat
- Level 2: at least 13 / 16
- Level 3: at least 15 / 16

## Case 1: quick terminology choice

User:

```text
“回答模板”这个词是不是不够准？
```

Expected routing:

```text
task_type: decision / writing
complexity_level: L1
selected_adapter: none or writing
```

Must include:

- direct judgment
- concise reason
- better alternative term

Avoid:

- full proposal structure
- framework history

## Case 2: ambiguous framework idea

User:

```text
我在思考一个大模型的输出框架，不削弱大模型能力，但让它更规范、更有架构感、更能交互。
```

Expected routing:

```text
task_type: framework_design
complexity_level: L2
selected_adapter: framework
```

Must include:

- reframe as dynamic answer protocol, not fixed template
- early judgment
- core layers
- one next step

Avoid:

- asking many clarifying questions before giving value
- presenting all sections as mandatory

## Case 3: methodology system upgrade

User:

```text
按方法论系统推进。
```

Expected routing:

```text
task_type: framework_design
complexity_level: L3
selected_adapter: framework
```

Must include:

- interpret as upgrading from usable protocol to methodology-backed system
- add framework map, hidden mechanisms, structured contract, evaluation cases
- explain why these layers preserve semantics
- produce or propose a deliverable

Avoid:

- only restating previous ideas
- ignoring packaging or implementation if the context is Skill creation

## Case 4: product feature request

User:

```text
帮我把这个回答协议做成一个产品功能。
```

Expected routing:

```text
task_type: product
complexity_level: L3
selected_adapter: product
```

Must include:

- target user
- user problem
- MVP scope
- must-haves and non-goals
- success metrics
- validation step

Avoid:

- jumping to UI components before defining user value
- making MVP too large

## Case 5: technical architecture

User:

```text
如果要把这个协议接到我们的内部 AI 平台，架构怎么设计？
```

Expected routing:

```text
task_type: technical
complexity_level: L3
selected_adapter: technical
```

Must include:

- background and goals
- constraints or assumptions
- recommended architecture
- alternatives and trade-offs
- implementation plan
- risks, monitoring, rollback or fallback

Avoid:

- only giving high-level product language
- omitting rejected alternatives

## Case 6: strategic choice

User:

```text
这个东西应该先做成开源方法论、企业内部规范，还是商业产品？
```

Expected routing:

```text
task_type: strategy / decision
complexity_level: L2 or L3
selected_adapter: strategy or decision
```

Must include:

- recommended path under stated or inferred criterion
- ranking of options
- what to deprioritize
- conditions that would change the recommendation

Avoid:

- equal-weight pros/cons without a decision

## Case 7: research synthesis

User:

```text
找找有没有类似理论，并判断我们这个框架有没有创新点。
```

Expected routing:

```text
task_type: research
complexity_level: L3
selected_adapter: research
```

Must include:

- external search and citations when required by environment
- distinction between known frameworks and user's synthesis
- clear innovation judgment
- uncertainty and scope

Avoid:

- relying only on memory for current or niche claims
- naming frameworks without operational comparison

## Case 8: critique request

User:

```text
你看看这个协议是不是太复杂，会不会让大模型变笨？
```

Expected routing:

```text
task_type: critique
complexity_level: L2
selected_adapter: critique
```

Must include:

- clear evaluation
- differentiate visible output from hidden mechanism
- identify bloat risks
- recommend simplification or guardrails

Avoid:

- defending the framework uncritically

## Case 9: execution planning

User:

```text
接下来一个月怎么验证这套协议有用？
```

Expected routing:

```text
task_type: execution
complexity_level: L3
selected_adapter: execution
```

Must include:

- phased plan
- test cases
- metrics
- baseline comparison
- review cadence
- decision gate

Avoid:

- only listing generic tasks

## Case 10: normal small writing task

User:

```text
帮我把这句话改得更正式：这个东西挺好用的。
```

Expected routing:

```text
task_type: writing
complexity_level: L1
selected_adapter: writing
```

Must include:

- the rewritten sentence
- optionally one variant

Avoid:

- need reconstruction
- proposal headings
- methodology discussion


## v0.3 evidence-governance supplement

For evidence-dependent cases, keep the original 16-point score and add this supplemental check. Score each item 0 to 2.

| Criterion | 0 | 1 | 2 |
|---|---|---|---|
| retrieval fit | no retrieval when needed, or unnecessary heavy retrieval | retrieval used but scope is vague | retrieval depth matches task and stakes |
| source appraisal | sources cited or mentioned without quality judgment | some quality notes | source quality, recency, directness, and incentives are weighed |
| completeness awareness | implies false completeness or omits gaps | generic caveat | clear completeness level and material gaps |
| evidence calibration | recommendation strength ignores evidence strength | partial calibration | judgment strength matches evidence strength |

Evidence-dependent answers should normally score at least 6 / 8 on this supplement unless the user only asked for a quick fact check.

## Case 11: evidence governance update

User:

```text
检索规范和信息批判性审查以及检索的完备性自觉，你认为应当加入到该skill当中吗？如果建议，列一下关于前面关键词的最佳既有实践或理论框架
```

Expected routing:

```text
task_type: framework_design / research_synthesis
complexity_level: L3
selected_adapter: framework + research
```

Must include:

- clear judgment that evidence and retrieval governance should be added as a layer, not a rigid visible template
- mapping of retrieval, source criticism, and completeness awareness to operating roles
- reference to best-practice frameworks such as ACRL, Cochrane, PRISMA/PRISMA-S, PRESS, SIFT, GRADE, AMSTAR 2, risk-of-bias tools, IR evaluation, and Toulmin-style argument checks
- distinction between visible answer behavior and hidden governance
- warning against citation theater and fake completeness

Avoid:

- replacing the core protocol with a research-only workflow
- forcing full systematic-review process into ordinary answers
- presenting frameworks as decorative theory names

## Case 12: evidence-dependent product recommendation

User:

```text
帮我判断现在应该选哪个向量数据库，最好给出依据。
```

Expected routing:

```text
task_type: technical / decision_support / research_synthesis
complexity_level: L3
selected_adapter: technical + decision + research
```

Must include:

- retrieval or verification if current product facts matter
- source-type awareness, including official docs, benchmarks, changelogs, pricing, and reputable user reports when available
- clear recommendation under stated assumptions
- alternatives and trade-offs
- evidence versus inference distinction
- completeness boundary, especially if benchmarks or prices may change

Avoid:

- relying only on remembered product reputation
- treating vendor benchmarks as neutral evidence
- giving a comparison table without a recommendation

## Regression tests

The skill fails if it repeatedly shows any of these behaviors:

- every answer uses the same seven headings
- simple edits become formal proposals
- complex decisions avoid recommendations
- frameworks are listed but not assigned operational roles
- user-facing answers expose hidden reasoning or chain-of-thought
- answers end with many questions instead of a useful next step
- product, technical, or decision tasks ignore their adapters
- current factual claims are made without required verification
- evidence-dependent answers cite sources without source appraisal
- answers imply comprehensive retrieval without scope, source universe, or completeness boundary

## Version acceptance checklist

Before releasing a new version, run at least five cases covering:

1. one Level 1 request
2. one Level 2 framework or critique request
3. one Level 3 formal deliverable
4. one adapter-heavy task, such as product or technical
5. one methodology/provenance question using `framework-map.md`
6. one evidence-dependent research or recommendation question using the evidence-governance supplement

A release is acceptable when each answer reaches the target score and no regression test fails.
