# Run Report Template

Use this template for `agent_tasks/reports/report-prd-[feature-name]-[YYYY-MM-DD].md`.

Derive `[feature-name]` from the PRD filename for traceability with `/verify`.

---

```markdown
---
PRD: agent_tasks/prd-[feature-name].md
Story: [story number or title]
Cycle date: [YYYY-MM-DD]
Verified: —
Verdict: —
---

# Cycle Run Report: [feature-name]
Task file: [path]

## Agent Audit

Every agent spawned during this cycle. **Model param set?** confirms the Agent tool call included an explicit `model` parameter (not inherited from parent).

| # | Phase | Purpose | Model requested | Model param set? | Spawned? | Completed? | Notes |
|---|---|---|---|---|---|---|---|
| 1 | — | — | — | — | — | — | — |

## Rescues

Silent substitutions and recoveries during the cycle (copied verbatim from cycle state). Each line: `ts | type | agent | description | resolution | artifact`. Empty = clean cycle.

- (or "None")

## Agent Telemetry

Aggregated from omp native session transcripts (`<id>.jsonl` artifacts + `history://<id>`) or the supplementary hook log (`agent_states/events/*.jsonl`). One row per `agent_id`. If no transcripts or event logs exist, write: *"Telemetry not collected."*

| Agent ID | Type | Tool calls | Breakdown | Errors | Wallclock | Stop reason |
|---|---|---|---|---|---|---|
| — | — | — | — | — | — | — |

### Phase-3 totals
| Metric | Value |
|---|---|
| Total tool calls | [n] |
| Total errors | [n] |
| Contradiction-exits | [n — count of `RESCUE contradiction-loop` events] |
| Phase-3 wallclock (first→last event) | [duration] |

### Supervisor health (5.5.5)
| Metric | Value |
|---|---|
| Status at cycle end | [active / disabled] |
| Spawns | [n] |
| Stalls | [n] |
| Uptime % | [(spawns - stalls) / spawns × 100, or "n/a" if spawns = 0] |
| Cycle classification | [normal / **degraded** — uptime <90% or status=disabled] |

## Supervisor recommendations (5.5.6)

Every `depth-recommendation` the supervisor emitted, with the orchestrator's decision. Copied verbatim from cycle state's `## Supervisor recommendations` section. Empty = no recommendations this cycle.

| ts | Suggestion | Accepted? | Rationale |
|---|---|---|---|
| — | — | — | — |

## Context Sources

Outcome of each Context Source consulted this cycle (per `.claude/config.md` § Context Sources). One row per (stage, source). `unavailable` / `DEGRADED` markers from graceful degradation land here. Empty = none enabled.

| Stage | Source | Outcome |
|---|---|---|
| — | — | consulted / unavailable / DEGRADED / disabled |

## Analyzer drift (5.8.1)

When `analyzer_baseline` is enabled, this section captures any new analyzer warnings introduced during the cycle (diff of Phase 4A analyze output vs. `cycle_reports/<feature>/analyzer-baseline.txt`). Empty = clean.

- (or "None" / "Baseline tracking disabled")

## Economy — Agent usage

| Phase | Task | Model | Est. tokens | Rework? |
|---|---|---|---|---|
| — | — | — | [small/med/large/xlarge] | — |

### Model escalations
- [or "none"]

### Model downgrades possible
- [or "none"]

## Efficiency — Execution

| Parent task | Sub-tasks | Completed | Rework | Blockers | Parallel? |
|---|---|---|---|---|---|
| — | — | — | — | — | — |

### Rework details
- What failed, what model fixed it, trivial or non-trivial?

### Blocker details
- What blocked, duration, resolution?

## Effectiveness — Quality

| Metric | Value |
|---|---|
| Acceptance criteria | [n] |
| Sub-tasks planned | [n] |
| Sub-tasks completed | [n] |
| Commits | [n] |
| Reattempted commits | [n] |
| Test failures caught | [n] |
| Analysis warnings caught | [n] |

### /verify results (if available)
| Verdict | Count |
|---|---|
| PASS / WEAK / INCOMPLETE / NO TEST / NO IMPL | [n] |

### Skill gaps observed
- [or "none"]

## Recommendations
- Model allocation changes (with evidence)
- Skill updates needed (with evidence)
- Task generation improvements
```

---

## Reporting guidelines

- **Estimate tokens**: small (<5k), medium (5–20k), large (20–50k), xlarge (50k+)
- **Be honest** about escalations and possible downgrades — this data tunes the pipeline
- **Capture skill gaps** — most valuable data for `/self-improve`
- **Agent Audit accuracy**: if you're unsure whether `model` was set on a spawn, record "uncertain" — do not guess "yes"

## Report archival

If >10 reports in `agent_tasks/reports/`, summarize oldest into `agent_tasks/agent_metrics.md` (cumulative metrics table) and delete the archived files.
