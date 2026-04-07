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
