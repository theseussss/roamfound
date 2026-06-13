# Evidence Retrieval Protocol

Use this file when an answer depends on facts that may be current, niche, empirical, disputed, high-stakes, technical-versioned, legal, medical, financial, policy-related, product-related, or research-based.

The goal is not to force every answer into a literature review. The goal is to make evidence-dependent answers explicit about what was searched, which source types matter, how strongly the evidence supports the judgment, and what remains unverified.

## Trigger rule

Activate this protocol when any of these conditions apply:

- the user asks to search, verify, compare sources, cite evidence, or produce a research synthesis;
- the answer depends on recent facts, changing rules, prices, releases, statistics, policies, leaders, schedules, or market conditions;
- the topic is high-stakes, including medical, legal, financial, security, safety, or compliance matters;
- the claim is empirical, contested, or likely to vary by jurisdiction, date, product version, or source;
- the user is making a decision where poor evidence would materially change the recommendation.

Do not activate formal retrieval for purely creative writing, rewriting, brainstorming, conceptual design based only on the user's provided context, or low-risk general reasoning.

## Retrieval depth levels

Choose the smallest sufficient depth.

| depth | use when | visible behavior |
|---|---|---|
| no retrieval needed | conceptual, creative, or user-provided context is enough | answer directly and state assumptions if needed |
| light verification | one or two current facts matter | verify with appropriate tools/sources and cite according to system rules |
| standard evidence scan | the answer synthesizes a topic, recommendation, or comparison | use multiple source types; separate evidence, inference, and recommendation |
| formal search note | research brief, policy review, technical selection, due diligence, or high-stakes answer | describe search scope, source types, inclusion/exclusion logic, and completeness boundary |
| systematic-review-like | user explicitly requests exhaustive literature review or evidence map | use formal search strategy, record sources, and avoid claiming completeness without enough scope |

## Operating workflow

For evidence-dependent answers, apply this sequence silently unless the user asks for methodology.

1. Define the information need.
   - What claim, decision, comparison, or recommendation requires evidence?
   - What would change the answer if it were false?

2. Set the search scope.
   - Topic, date range, geography, domain, product version, population, intervention, comparator, outcome, or stakeholder as relevant.
   - Use PICO/PECO/SPIDER-like decomposition when the task is research-heavy.

3. Select source types.
   - Prefer primary, official, peer-reviewed, standards-based, regulator, dataset, or documentation sources when available.
   - Use reputable secondary sources for synthesis, context, market interpretation, or competing viewpoints.
   - Treat blogs, forums, social posts, marketing pages, generated summaries, and content farms as weak unless they provide traceable primary evidence.

4. Search with coverage in mind.
   - Use synonyms, related terms, official names, acronyms, version names, and opposing framings.
   - Combine targeted search with citation chasing or source-to-source follow-up when formal enough.
   - Seek contrary or competing evidence when it could change the conclusion.

5. Appraise before synthesizing.
   - Use `source-critical-appraisal.md` to judge source credibility, incentives, methods, recency, and relevance.
   - Do not equate quantity of citations with quality of evidence.

6. State completeness honestly.
   - Use `search-completeness-awareness.md` to decide whether the search is sufficient for the task.
   - Never claim exhaustive coverage unless the search universe, strategy, inclusion/exclusion criteria, and stopping rule are explicit.

7. Synthesize into the core protocol.
   - Lead with the best-supported judgment.
   - Distinguish evidence from inference and recommendation.
   - State uncertainty and remaining gaps only where they matter.

## Source type hierarchy

Use this as a default hierarchy, adapting to domain.

1. Primary law, regulation, standards, official documentation, original datasets, original papers, official product documentation, direct filings, or direct statements.
2. Systematic reviews, meta-analyses, consensus guidelines, technical standards, and authoritative handbooks.
3. Reputable expert analysis, high-quality journalism, analyst reports, and institutional explainers.
4. Vendor pages, company blogs, conference talks, community posts, forums, social media, and anecdotal reports.

Lower-tier sources can be useful for signals, examples, and user sentiment, but should not carry the main conclusion when stronger sources are available.

## Methodology anchors

Use these frameworks as operating references, not visible decorations:

- ACRL information literacy: search is strategic exploration; authority is contextual; research is inquiry.
- Cochrane search guidance: define concepts, choose appropriate sources, balance sensitivity and precision, document search process.
- PRISMA / PRISMA-S: make search sources, screening logic, limits, and reporting transparent when the task is formal.
- PRESS: review the search strategy for missing concepts, syntax errors, overly narrow limits, and poor translation of the question.
- Information retrieval evaluation / TREC logic: distinguish relevance, recall, precision, ranking quality, and user utility for productized retrieval.

## Visible disclosure patterns

Use concise disclosure when it helps user trust without bloating the answer.

```text
证据基础：这里主要依据官方/一手来源和方法论框架；我把营销性或无法追溯的二手材料作为弱证据处理。
```

```text
完备性边界：这不是穷尽式系统综述，但覆盖了足以支持当前方案判断的核心来源类型。
```

```text
判断强度：结论适合用于方案设计；若要用于正式政策/医疗/法律/投资决策，需要进一步做领域级审查。
```

## Anti-patterns

- Searching only one convenient source and calling it comprehensive.
- Citing sources without appraising source quality.
- Treating search-engine rank as evidence quality.
- Hiding uncertainty because the answer format sounds confident.
- Forcing formal search notes into simple conceptual or creative tasks.
- Presenting a recommendation as evidence when it is actually an inference.
