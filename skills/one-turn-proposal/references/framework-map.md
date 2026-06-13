# Framework Map

Use this file when the user asks where the protocol comes from, whether existing frameworks were integrated, whether semantics were lost, or how to turn the protocol into a methodology system. The goal is traceability without theory dumping.

## Integration principle

Do not place every framework in the visible answer. Assign each framework to one of five roles:

1. **core protocol**: always influences complex answers.
2. **task adapter**: used only for matching domains.
3. **hidden mechanism**: shapes internal comparison, verification, or self-repair.
4. **engineering contract**: used for productization, agents, schemas, or evaluation.
5. **excluded or softened**: useful idea, but harmful if treated as a default rule.

When explaining the methodology, show the operating role, not just the framework name.

## Framework integration table

| source framework | role in this skill | retained semantics | what is intentionally compressed or excluded |
|---|---|---|---|
| human-ai interaction guidelines | core protocol + interaction layer | reconstruct need, set expectations, avoid unnecessary blocking, expose uncertainty, leave a useful next step | the full guideline taxonomy is not shown to the user |
| pyramid principle | core protocol + answer expression | judgment first, supporting structure, sections that serve the conclusion | formal consulting terminology is usually hidden |
| scqa | problem framing inside core protocol | situation, complication, question, answer become need, tension, real question, judgment | the acronym is only used when discussing methodology |
| adr | decision and boundary logic | decision context, selected option, rejected alternatives, consequences, re-evaluation conditions | full architecture-record format is used only for decision deliverables |
| prd | product adapter | user, pain point, goals, non-goals, requirements, metrics, validation | not used outside product/feature work |
| pr-faq / working backwards | product and innovation adapter | customer problem, future value, objections, faqs, why now | not used as a default answer format |
| rfc | technical adapter | context, goals, constraints, proposal, alternatives, rollout, risks, open questions | not used for non-technical answers |
| react | hidden verification mechanism | when information may be current, factual, tool-dependent, or high-stakes, verify with tools and cite evidence as required | do not expose action loops or private reasoning |
| tree of thoughts | hidden comparison mechanism | consider multiple possible routes, evaluate, choose one, state rejected alternatives when useful | do not display a full thought tree |
| self-refine | hidden quality-control mechanism | silently check and repair missing judgment, missing next step, over-template output, weak boundaries | do not show iterative self-critique unless requested |
| reflexion / memory | optional long-term improvement mechanism | adapt to user preferences and prior feedback when platform memory or conversation context supports it | not part of the one-turn core; do not assume persistent memory exists |
| structured outputs / json schema | engineering contract | separate natural-language answer from machine-readable fields for agents, evals, or workflows | do not show json to ordinary users by default |
| prompt pattern catalog | template and behavior design | reusable patterns, examples, format defaults, flipped interaction when helpful | not treated as a user-facing theory list |
| mece | softened structuring principle | reduce obvious overlap and make categories decision-useful | do not force fake completeness |
| persona prompting | excluded as core, optional tone aid | can lightly adjust stance and register | not relied on for quality because roleplay does not guarantee judgment |


## Evidence and retrieval framework map

Use this section when the user asks about retrieval norms, evidence criticism, search completeness, or whether evidence-related semantics were preserved. These frameworks are not meant to appear in every answer; they supply operating roles for evidence-dependent answers.

| source framework / practice | role in this skill | retained semantics | what is intentionally compressed or excluded |
|---|---|---|---|
| acrl information literacy framework | evidence philosophy layer | search as strategic exploration; authority is contextual; research is inquiry; scholarship is conversation | do not show the full educational taxonomy in normal answers |
| cochrane search guidance | formal research retrieval adapter | question decomposition, source selection, sensitivity/precision balance, search documentation, citation chasing | not applied to simple conceptual or creative tasks |
| prisma 2020 | transparent evidence-flow reporting | sources searched, screening logic, included/excluded evidence, limits of synthesis | no flow diagram unless the user asks for formal review output |
| prisma-s | search-reporting discipline | database/source names, platforms, dates, search strategies, limits, reproducibility | report quality is not treated as evidence quality by itself |
| press | search strategy review | check whether the search translates the question correctly, covers concepts, uses appropriate syntax, and avoids over-narrow filters | full peer review is only for systematic-review-like tasks |
| sift / lateral reading | web-source criticism | stop, investigate source, find better coverage, trace to original context, verify source reputation outside the page | not reduced to superficial checklist scoring |
| craap / cars / radar | lightweight source screening | currency, relevance, authority, accuracy, purpose, reasonableness | softened because checkbox completion can create false confidence |
| grade | certainty and recommendation-strength calibration | risk of bias, inconsistency, indirectness, imprecision, publication bias, strong vs conditional recommendation | not used mechanically outside empirical evidence tasks |
| amstar 2 | review-quality appraisal | inspect systematic reviews for search adequacy, bias assessment, synthesis method, conflicts, and critical weaknesses | no single numeric score by default |
| rob 2 / robins-i / rob-me | bias-awareness toolkit | selection, confounding, measurement, missing data, selective reporting, missing evidence | only invoked for study/evidence review tasks |
| information retrieval evaluation / trec | productized retrieval evaluation | precision, recall, ranking, relevance judgments, test collections, user utility | engineering metrics do not replace human source appraisal |
| toulmin / argument mapping | reasoning support check | claim, evidence, warrant, qualifier, rebuttal | do not expose as formal argument diagram unless useful |

## Layer assignment

```text
visible answer layer
  - need reconstruction
  - core judgment
  - purposeful structure
  - proposal or artifact
  - risk and boundary
  - next interaction entry

methodology layer
  - framework map
  - problem framing
  - task adapters
  - complexity levels
  - anti-patterns

hidden mechanism layer
  - multi-path comparison
  - tool verification
  - self-repair
  - interaction routing
  - memory only when available

evidence and retrieval layer
  - retrieval trigger and depth
  - source appraisal
  - evidence versus inference separation
  - contrary-source check
  - completeness boundary

engineering layer
  - structured output contract
  - evaluation cases
  - acceptance criteria
```

## Semantic preservation rules

Use these rules when asked whether the methodology lost meaning during integration:

1. **preserve function over name**: it is acceptable to remove framework names if their operating function remains.
2. **compress ceremony, not judgment**: remove formal labels and rigid sections, but keep decision logic and trade-offs.
3. **hide mechanisms, show conclusions**: do not show full reasoning trees or self-refinement loops; show the selected path and concise rationale.
4. **separate general core from domain adapters**: prd, rfc, adr, and pr-faq should not pollute all answers.
5. **state intentional exclusions**: if a framework is excluded or softened, say why when the user is discussing methodology.
6. **avoid false universality**: the protocol is best for complex, ambiguous, proposal-like tasks; simple requests should be compressed.
7. **preserve evidence discipline over citation display**: a citation or source list is not enough; preserve the ability to decide when retrieval is needed, which sources matter, how reliable they are, and how complete the search is.

## How to explain integration to the user

Use this pattern:

```text
我的判断是：没有把这些框架平铺进去，而是分层归位。

核心层保留了 human-ai interaction、金字塔原理、scqa、adr 和 self-refine 的操作语义。
场景层保留了 prd、rfc、pr-faq、咨询提案等专用结构。
隐性层保留了 react、tree of thoughts、self-refine 的机制，但不把推理过程完整展示给用户。
证据层保留 ACRL、Cochrane、PRISMA-S、PRESS、SIFT、GRADE 等框架的操作语义，用于检索触发、来源审查、证据强度和完备性边界。
工程层保留 structured outputs 的思想，用于产品化和评估。

所以丢掉的是理论标签和仪式感，不是关键语义。
```

## Common methodology mistakes

- Listing frameworks without assigning them to layers.
- Treating all frameworks as equally important.
- Making every answer look like a formal consulting report.
- Showing hidden reasoning mechanisms as if they were user-facing content.
- Calling something a methodology without evaluation cases or failure modes.
- Confusing output consistency with answer quality.

- Treating citations as proof instead of appraising source quality.
- Claiming comprehensive search when the source universe, search strategy, and stopping rule are not defined.
- Applying formal systematic-review procedures to low-risk conceptual or creative tasks.
