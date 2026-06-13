# Structured Output Contract

Use this file only when the user asks for productization, agent integration, api usage, consistency checks, evaluation, analytics, or machine-readable outputs. Do not show json by default in ordinary user-facing answers.

For strict validation, use the optional schema at `schemas/one-turn-proposal.schema.json`.

## Purpose

The natural-language answer is optimized for the user. The structured contract is optimized for systems that need to inspect, route, evaluate, or store the answer.

The two layers should remain separate:

```text
user-facing answer: concise, natural, judgment-led
system-facing contract: typed fields, stable keys, evaluation hooks
```

## Recommended sidecar object

Use this object as a sidecar state, not as the default user-facing response.

```json
{
  "protocol_version": "0.3",
  "task_type": "framework_design",
  "complexity_level": "l3_formal_proposal",
  "need_reconstruction": "the user wants a reusable answer methodology, not a rigid template.",
  "assumptions": ["the answer should remain natural and adaptive"],
  "core_judgment": "build this as a dynamic protocol with adapters and hidden mechanisms.",
  "judgment_type": ["recommendation", "tradeoff"],
  "dominant_criterion": "preserve model flexibility while improving answer consistency",
  "structure": [
    {"section": "core protocol", "purpose": "define the default answer loop"},
    {"section": "task adapters", "purpose": "specialize by domain"},
    {"section": "quality checks", "purpose": "repair common failures"}
  ],
  "recommendation": "use a skill with references files rather than a single long prompt.",
  "alternatives_considered": [
    {"name": "fixed template", "benefit": "simple", "cost": "rigid", "selected": false},
    {"name": "dynamic protocol", "benefit": "adaptive", "cost": "requires routing", "selected": true}
  ],
  "execution_path": ["define protocol", "add adapters", "add checks", "test with eval cases"],
  "risks_and_boundaries": ["simple questions should not trigger formal proposals"],
  "evidence_basis": "user_provided_context",
  "retrieval_required": false,
  "retrieval_trigger": "not_required",
  "search_scope": "not applicable; the user is designing a methodology from provided context",
  "source_types_used": [],
  "search_strategy_summary": "not applicable",
  "source_appraisal": [],
  "contrary_or_competing_evidence_checked": false,
  "completeness_level": "not_applicable",
  "known_gaps": [],
  "confidence_basis": "the recommendation is based on the user-provided design goal and internal methodology reasoning",
  "uncertainty": "low",
  "next_step": "test the protocol against representative requests.",
  "adapter_used": "none",
  "quality_flags": [],
  "semantic_map_used": true
}
```

## Field guidance

- `protocol_version`: use the version of this methodology contract.
- `task_type`: choose the closest task category from the schema.
- `complexity_level`: choose the smallest sufficient depth.
- `need_reconstruction`: one or two sentences about the real user need.
- `assumptions`: reasonable defaults used to proceed.
- `core_judgment`: must be a position, not a summary.
- `judgment_type`: label the judgment behavior: recommendation, priority, tradeoff, rejection, confidence, or condition.
- `dominant_criterion`: the main criterion that drove the recommendation.
- `structure`: sections or modules used, with the purpose of each.
- `recommendation`: the selected path when applicable.
- `alternatives_considered`: include only meaningful alternatives; do not create filler options.
- `execution_path`: concrete steps, not abstract virtues.
- `risks_and_boundaries`: only material boundaries, not generic disclaimers.
- `evidence_basis`: distinguish internal reasoning, user-provided context, cited sources, tool results, mixed, or not required.
- `retrieval_required`: whether external retrieval or verification was needed.
- `retrieval_trigger`: why retrieval was or was not required.
- `search_scope`: what topics, dates, source universe, jurisdiction, version, or population were covered.
- `source_types_used`: source classes used, such as official documentation, peer-reviewed research, standards, datasets, reputable journalism, or user-provided material.
- `search_strategy_summary`: concise description of how retrieval was approached; omit detailed logs unless needed.
- `source_appraisal`: source-quality notes when evidence quality affects the answer.
- `contrary_or_competing_evidence_checked`: whether material disagreement or contrary evidence was considered.
- `completeness_level`: not_applicable, single_source_check, sufficient_for_answer, representative_not_exhaustive, systematic_review_like, or insufficient.
- `known_gaps`: important missing evidence, source limitations, or coverage limits.
- `confidence_basis`: why the stated confidence level is justified.
- `uncertainty`: uncertainty in the recommendation under stated assumptions.
- `next_step`: one best next move.
- `adapter_used`: prd, pr_faq, rfc, adr, decision_memo, consulting_proposal, writing_brief, research_synthesis, review, project_plan, or none.
- `quality_flags`: any remaining quality concerns after self-repair.
- `semantic_map_used`: true when framework-map traceability shaped the answer.

## User-facing disclosure pattern

When the user asks for both a normal answer and structured metadata, use:

````text
## Answer
[natural proposal-grade answer]

## Structured contract
```json
{ ... }
```
````

When the user only asks for a human-facing answer, omit the structured contract.

## Evaluation hooks

A system can score the answer using these fields:

| criterion | field evidence |
|---|---|
| understood user need | `need_reconstruction` |
| made a judgment | `core_judgment`, `judgment_type` |
| chose appropriate depth | `complexity_level` |
| avoided theory dumping | `semantic_map_used`, `structure.purpose` |
| produced action | `execution_path`, `next_step` |
| bounded answer | `assumptions`, `risks_and_boundaries`, `uncertainty` |
| handled evidence | `evidence_basis`, `source_appraisal`, `confidence_basis` |
| governed retrieval | `retrieval_required`, `retrieval_trigger`, `search_scope`, `source_types_used` |
| bounded completeness | `completeness_level`, `known_gaps`, `contrary_or_competing_evidence_checked` |
| compared options | `alternatives_considered` |

## Anti-patterns

- Emitting json in every answer.
- Treating the json contract as a substitute for a good answer.
- Filling fields with generic phrases.
- Listing frameworks that did not actually shape the answer.
- Using low uncertainty when material assumptions are unresolved.
- Letting the sidecar schema force a heavy visible answer.
- Marking retrieval as complete without source scope and stopping logic.
- Filling evidence fields with citations but no appraisal or completeness boundary.
