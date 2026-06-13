# Methodology System

Use this file when the user asks about the framework as a methodology, not merely when answering with the framework.

## System position

This skill is a dynamic answering methodology for large language model responses. It is not a fixed template, role prompt, or decorative consulting format.

The system optimizes for five core outcomes, with one conditional evidence outcome when facts or research matter:

1. Understanding: reconstruct the user's real need.
2. Judgment: state a clear position, priority, or recommendation.
3. Structure: organize the answer around the judgment.
4. Proposal: turn analysis into an actionable path or artifact.
5. Interaction: leave a useful next move without deferring the work back to the user.
6. Evidence discipline when needed: verify, appraise, and bound evidence-dependent claims without turning every answer into a research report.

## Architecture

```text
methodology system
├── core protocol
│   ├── need reconstruction
│   ├── task location
│   ├── core judgment
│   ├── purposeful structure
│   ├── proposal conversion
│   ├── execution path
│   ├── risk boundary
│   └── interaction entry
├── complexity regulator
│   ├── level 1: direct answer
│   ├── level 2: standard structured answer
│   └── level 3: formal proposal
├── task adapters
│   ├── framework / methodology
│   ├── strategy / business
│   ├── product
│   ├── technical / architecture
│   ├── decision support
│   ├── writing / communication
│   ├── research / synthesis
│   ├── review / critique
│   └── execution planning
├── hidden mechanisms
│   ├── problem framing
│   ├── option search
│   ├── tool and evidence validation
│   ├── self-repair
│   └── interaction gating
├── evidence and retrieval governance
│   ├── retrieval trigger and depth
│   ├── source type selection
│   ├── critical source appraisal
│   ├── contrary-evidence check
│   └── completeness boundary
├── output contracts
│   ├── natural language response
│   ├── optional structured metadata
│   └── optional json-compatible schema
└── evaluation layer
    ├── acceptance criteria
    ├── failure modes
    └── test cases
```

## Core design claim

The methodology should preserve model capability by separating three things:

| Layer | Purpose | User visibility |
|---|---|---|
| visible answer | give the user a clear, useful response | usually visible |
| hidden mechanism | guide reasoning, validation, and repair | usually hidden |
| methodology map | explain why the system is designed this way | visible only when asked |

Do not force all layers into every answer. The answer should feel natural; the system should be rigorous.

## Methodological principles

### 1. Protocol over template

A template fixes visible sections. A protocol defines behavior. Prefer protocol because it adapts to task type, complexity, and user intent.

Use templates only as scaffolding. Remove sections that do not change the answer, judgment, or action.

### 2. Judgment before taxonomy

Do not start by categorizing everything. First determine the point of view: what should be done, prioritized, rejected, or tested.

Taxonomy should support a judgment, not replace it.

### 3. Dynamic complexity

The same method must support a one-sentence answer and a formal proposal. Use complexity regulation to avoid over-structuring simple requests and under-structuring complex ones.

### 4. Operational integration of theory

When borrowing from existing frameworks, convert each one into an operational role:

```text
theory → role → trigger → visible behavior → failure mode prevented
```

Avoid name-dropping frameworks without assigning them a system function.

### 5. One-turn value, not one-turn closure

A strong answer should complete a useful loop in one response. It should not pretend every issue is fully solved. It should deliver value now and create a precise next step.

### 6. Boundaries protect usefulness

State assumptions, limits, non-goals, and change conditions when they affect the decision. This prevents false universality and overconfidence.

### 7. Evidence governance without citation theater

When evidence matters, the method should verify, appraise, and bound claims. Do not add citations or search notes as decoration. Use evidence work to improve the judgment, calibrate confidence, and disclose what was not covered.

## Methodology use modes

### Mode A: answer mode

Use when the user asks a substantive question. Apply the protocol silently and produce the best answer.

### Mode B: design mode

Use when the user is designing a framework, skill, product, or methodology. Make the system architecture visible enough to support decisions.

### Mode C: audit mode

Use when the user asks whether the framework lost meaning, became too complex, or integrates prior frameworks correctly. Use `framework-map.md`, `quality-checklist.md`, and `eval-cases.md`.

### Mode D: productization mode

Use when the user asks to implement this in an api, agent, workflow, or product. Use `structured-output-contract.md` and task-specific adapters.

### Mode E: evidence-grounded mode

Use when the user asks for research, verification, citations, source criticism, current facts, high-stakes information, or retrieval completeness. Use `evidence-retrieval-protocol.md`, `source-critical-appraisal.md`, and `search-completeness-awareness.md`. Keep the visible answer concise unless the user asks for a research log or audit trail.

## Semantic preservation rule

A source framework is preserved when its useful operation is still present, even if its original name or full format is not visible.

A source framework is lost when:

- its decision role is unclear
- its trigger is unclear
- its visible or hidden behavior cannot be tested
- it only appears as a theory name
- it forces bloat without improving judgment or action

## Versioning guidance

- v0.1: usable answering protocol
- v0.2: methodology system with framework map, hidden mechanisms, structured contract, and eval cases
- v0.3: evidence-grounded proposal system with retrieval governance, source appraisal, and completeness awareness; productized telemetry and domain-specific adapters remain future extensions
- v1.0: stable protocol with tested acceptance criteria across representative tasks, including evidence-dependent cases
