# Search Completeness Awareness

Use this file to decide whether retrieval is sufficient for the user's task and how to disclose search limits honestly.

Completeness awareness does not mean every answer must be exhaustive. It means the assistant should know what level of coverage is appropriate, avoid fake completeness, and state boundaries when evidence affects the judgment.

## Completeness levels

| level | meaning | acceptable language |
|---|---|---|
| not_applicable | no retrieval was needed | no disclosure required |
| single_source_check | a specific fact or official source was checked | "基于该来源/官方页面..." |
| sufficient_for_answer | enough evidence for a practical answer | "足以支持当前判断" |
| representative_not_exhaustive | covers major source types or frameworks, not all possible material | "代表性覆盖，不是穷尽综述" |
| systematic_review_like | formal search strategy, screening, and documentation were used | "接近系统综述式检索，但仍以声明范围为准" |
| insufficient | evidence is too thin, conflicting, inaccessible, or not searched | "目前证据不足以做强判断" |

## Sufficiency questions

Before presenting an evidence-dependent answer, ask silently:

1. Have I covered the source types that matter for this task?
2. Have I checked whether stronger primary or official sources exist?
3. Would a reasonable contrary source change the judgment?
4. Are there date, geography, language, jurisdiction, product-version, or population limits?
5. Did later sources merely repeat the same origin, or provide independent confirmation?
6. Would a formal decision require a deeper search than this answer performed?
7. Can I honestly call this complete, or only sufficient for the current purpose?

## Completeness tactics

Use these when the task requires more than a light check.

### Known-item recall

If there are known key documents, standards, papers, or official sources, check whether the search finds them. If it does not, the search strategy may be too narrow or poorly phrased.

### Citation chasing

Follow references backward to earlier primary sources and forward to later citing work when the topic is research-heavy or methodologically sensitive.

### Relative recall

Compare search results against a set of known relevant sources. If many relevant sources are missing, revise the search rather than synthesizing prematurely.

### Diminishing returns / stopping rule

A practical search can stop when:

- new searches mainly repeat already-seen sources;
- stronger source types have been checked;
- contrary searches do not materially change the judgment;
- the answer's intended use does not justify formal exhaustive review;
- remaining gaps are disclosed.

Do not use this stopping rule for explicit systematic reviews, regulatory evidence reviews, litigation, clinical decisions, or other tasks where formal completeness is required.

### PRISMA-style evidence flow

For formal research answers, keep track of:

```text
sources searched → records or documents found → screened out → included → used for which claims
```

Do not display a full flow diagram unless the user asks, but preserve the logic.

## Disclosure patterns

Use the lightest disclosure that keeps the answer honest.

```text
完备性判断：这足以支持一个方案设计判断，但不是学术级穷尽综述。
```

```text
检索边界：我优先看官方文档、方法论手册和同行评议资料；没有把论坛讨论和营销材料作为主证据。
```

```text
不确定性：如果要用于正式投资/医疗/法律/政策决策，需要补做领域级检索和专家审查。
```

```text
证据不足：目前只能给出候选方向，不能给出强结论。下一步应先补充一手数据或权威来源。
```

## When not to claim completeness

Do not claim comprehensive coverage when:

- only web search was used;
- the search terms, date, source universe, and filters are not recorded;
- the topic crosses languages, jurisdictions, disciplines, or product versions;
- there is no contrary-source check;
- sources are mostly secondary or circular;
- the task would normally require expert review or database search.

## Anti-patterns

- Saying "all research shows" without a defined source universe.
- Treating the first page of results as complete.
- Confusing confidence in writing with confidence in evidence.
- Omitting search limits because they make the answer look less decisive.
- Overstating uncertainty after a sufficient practical search.
