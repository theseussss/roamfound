# Source Critical Appraisal

Use this file to judge whether retrieved information is credible, relevant, current, and strong enough to support a claim or recommendation.

The goal is to make the answer evidence-aware without turning every response into an academic review.

## Core distinction

Always separate three layers:

```text
evidence: what a source, dataset, document, or tool result directly supports
inference: what the assistant reasonably concludes from that evidence
recommendation: what the user should do under stated goals and constraints
```

Do not let a weak evidence base produce a strong recommendation unless the answer explicitly states that the recommendation is provisional.

## Fast appraisal workflow

1. Identify the source.
   - Who created it, when, and for what purpose?
   - Is it primary, secondary, interpretive, promotional, anecdotal, or generated?

2. Check authority in context.
   - Is this source authoritative for this specific question?
   - Is the authority official, methodological, empirical, experiential, or commercial?

3. Check method and traceability.
   - Does the source explain how it knows what it claims?
   - Are data, citations, methodology, or original context available?

4. Check recency and stability.
   - Does the fact change over time?
   - Is the source date appropriate for the claim?

5. Check bias and incentives.
   - Who benefits if the reader believes this?
   - Are conflicts of interest, selection effects, or marketing motives material?

6. Check agreement and disagreement.
   - Do independent high-quality sources converge?
   - Is there credible contrary evidence or meaningful expert disagreement?

7. Calibrate answer strength.
   - Strong evidence can support strong judgment.
   - Mixed or indirect evidence should produce conditional judgment.
   - Thin evidence should produce tentative judgment or a verification plan.

## Practical frameworks to preserve

Use the operation of these frameworks, not necessarily their names.

### SIFT / lateral reading

Use for web information, news, claims, screenshots, social media, and unfamiliar sources.

- Stop before trusting or sharing.
- Investigate the source.
- Find better or independent coverage.
- Trace claims, quotes, images, and data back to original context.
- Read laterally: leave the page and see how credible third parties describe the source or claim.

### CRAAP / CARS / RADAR, softened

Use only as a quick screening aid:

- currency: is it recent enough?
- relevance: does it directly answer the question?
- authority: is the author or institution credible here?
- accuracy: can the claim be checked?
- purpose: is the source informing, persuading, selling, entertaining, or manipulating?

Do not treat checklist completion as proof of reliability.

### GRADE-like certainty calibration

Use when the answer depends on bodies of empirical evidence, guidelines, policy research, or health-related claims.

Consider:

- risk of bias;
- inconsistency across studies or sources;
- indirectness relative to the user's question;
- imprecision or small sample/data limits;
- publication or reporting bias;
- magnitude of effect and plausible confounding where relevant.

Translate this into answer language:

```text
高确定性：多个高质量来源一致，且直接回答问题。
中等确定性：来源较强，但存在场景差异、间接性或限制。
低确定性：证据薄弱、冲突明显、依赖二手材料或缺少关键数据。
```

### AMSTAR 2 and review appraisal

Use when a source is itself a systematic review or meta-analysis.

Check whether it has:

- explicit research question and inclusion criteria;
- adequate search strategy;
- duplicate study selection or extraction when relevant;
- risk-of-bias assessment;
- appropriate synthesis method;
- handling of heterogeneity;
- disclosure of funding or conflicts;
- attention to publication bias or missing evidence.

Do not assume a paper is reliable merely because it is called a systematic review.

### Risk-of-bias tools

Use the logic of RoB 2, ROBINS-I, ROBINS-E, and ROB-ME when reviewing empirical studies or evidence syntheses:

- selection bias;
- confounding;
- measurement bias;
- missing data;
- selective reporting;
- missing or unpublished evidence.

### Toulmin / argument mapping

Use for reasoning quality:

```text
claim: what is being asserted?
evidence: what supports it?
warrant: why does that evidence imply the claim?
qualifier: how strong is the claim?
rebuttal: what would weaken or overturn it?
```

This prevents confident claims that are only loosely connected to evidence.

## Source quality labels

Use these labels internally or in structured metadata.

| label | meaning |
|---|---|
| high | primary/official/peer-reviewed/methodologically strong and directly relevant |
| medium | reputable but secondary, indirect, older, or limited in scope |
| low | promotional, anecdotal, unverified, biased, unsourced, or weakly relevant |
| mixed | useful but conflicting, incomplete, or varying by context |
| not_applicable | evidence appraisal is not needed for this task |

## Visible patterns

```text
我会把这个来源当作中等证据：它来自可靠机构，但不是一手数据，且只覆盖部分场景。
```

```text
这里的建议是条件性的，因为证据方向一致，但还缺少与你所在场景完全匹配的数据。
```

```text
这个结论不能只靠厂商材料支撑，需要至少补一个第三方评测或官方技术文档。
```

## Anti-patterns

- Counting citations instead of weighing evidence.
- Trusting a source because it is polished, popular, or highly ranked.
- Treating vendor claims as neutral evidence.
- Treating a single study as a settled consensus.
- Ignoring dates for fast-changing facts.
- Summarizing both sides without judging source strength.
