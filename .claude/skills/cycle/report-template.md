# Run Report Template

Use this template for `agent_tasks/reports/report-prd-[feature-name]-[YYYY-MM-DD].md`.

Derive `[feature-name]` from the PRD filename for traceability with `/verify`.

---

```markdown
---
PRD: agent_tasks/prds/prd-[feature-name].md
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
| Cycle classification | [normal / **degraded** — uptime <90% or status=disabled; `reason:harness-unsupported` and `reason:skip-flag` are **normal**, not degraded] |

## Gate wait

Output of `python3 .claude/skills/cycle/gate-report.py`, pasted. Captured automatically by the
Stop/UserPromptSubmit hook — nothing here is logged by hand.

Human gate-wait is usually the largest non-agent cost in a cycle and the constraint on how many
cycles one person can run at once, yet it is invisible in wallclock alone. If the script says
**not captured**, write that — it means the hooks are not wired, which is a different claim from
nobody having waited. An `OPEN gate` line means the cycle was still parked when the report was
written; reproduce it rather than omitting it.

| Gate | n | Total | Median | Max |
|---|---|---|---|---|
| — | — | — | — | — |

| Metric | Value |
|---|---|
| Total gate wait | [duration — the operator-bound share of wallclock] |
| Intervals logged / classified as gates | [n / n] |
| Open gate at report time | [none, or gate name + how long it has been waiting] |

## Supervisor recommendations (5.5.6)

Every `depth-recommendation` the supervisor emitted, with the orchestrator's decision. Copied verbatim from cycle state's `## Supervisor recommendations` section. Empty = no recommendations this cycle.

| ts | Suggestion | Accepted? | Rationale |
|---|---|---|---|
| — | — | — | — |

## Interruptions — parks, resumes and stops

Every point at which this cycle stopped and restarted, and what it cost. Empty = the cycle ran
start to finish in one session.

This is the only evidence that resume works. Under fan-out it is also the measurement behind
gate-throughput planning, so record it even when the cycle was otherwise unremarkable.

| ts | Type | Phase / gate | Reason | Waited | Outcome |
|---|---|---|---|---|---|
| — | park / resume / stop / limit-pause / reap | — | — | — | — |

- **park** — cycle wrote a gate request and exited. `Waited` is filled in by the *resume* row.
- **resume** — restarted from a state file or park bundle. Outcome records whether the resume was
  clean, or what had to be reconstructed: a moved base SHA, a stale approval, missing digests.
- **stop** — ended without releasing (blocker, contradiction-exit, user halt).
- **limit-pause** — the § Usage limits path fired.
- **reap** — the clone was abandoned and reclaimed by the dispatcher.

### Parallel context
| Field | Value |
|---|---|
| Cycles active during this run | [n, or 1 if run solo] |
| Framework commit | [sha — detects whether concurrent cycles ran the same instructions] |
| Base SHA at start → at release | [sha → sha; equal means the base did not move under this cycle] |
| Total parked duration | [sum of waits — the operator-bound share of wallclock] |

**Wallclock is not comparable across cycles without this.** A 4-hour cycle that spent 3 hours
parked on a gate and a 4-hour cycle that spent 4 hours working are different failures.

## Context Sources

Outcome of each Context Source consulted this cycle (per `.omp/agent-config.md` § Context Sources). One row per (stage, source). `unavailable` / `DEGRADED` markers from graceful degradation land here. Empty = none enabled.

| Stage | Source | Outcome |
|---|---|---|
| — | — | consulted / unavailable / DEGRADED / disabled |

## Analyzer drift (5.8.1)

When `analyzer_baseline` is enabled, this section captures any new analyzer warnings introduced during the cycle (diff of Phase 4A analyze output vs. `agent_states/analyzer-baseline-<feature>.txt`). Empty = clean. **Not recorded** is a distinct outcome from clean — say which, since the baseline is per-cycle scratch and can legitimately be absent.

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

### Permission prompts (probe 12)

Every permission prompt this cycle raised. `gate-report.py` now measures the *wait* automatically
(`PermissionRequest` → `PostToolUse`, logged as `gate=permission`), so paste its permission lines
here rather than reconstructing durations from memory. What it cannot know is still yours to write:
which agent asked, what the agent was trying to do, and whether the right fix is a grant or a
scoped script. An `OPEN permission ask` line means the cycle is blocked on one right now —
reproduce it. Empty means none appeared, which is itself worth stating.

| Agent | Command | Doing what | Outcome | Grant or script? |
|---|---|---|---|---|
| — | — | — | approved / denied / worked around | — |

A prompt approved every run is a grant waiting to be written down. One worked around every run is a
script waiting to be written. One the *orchestrator* absorbed is probe 10 as well. See
`harness-findings` § Probe 12 for how to choose.

### Falsification integrity (verify Step 4c)
| Metric | Value |
|---|---|
| Guards with falsification evidence | [n] |
| Re-run by verify | [n — or `0 — depth: lite`] |
| Reproduced | [n] |
| **Did not reproduce** | [n — any non-zero is a Harness finding, not a code finding] |

A test whose falsification does not reproduce is unproven whatever the suite says, and it puts
the cycle's other evidence in doubt too. Record the count even when it is zero: "re-ran 6, all
reproduced" and "re-ran none" are different cycles, and only the first is evidence of anything.

### Skill gaps observed
- [or "none"]

## Harness findings

Process faults from this cycle, independent of whether the work shipped. Work the probe
checklist in the `harness-findings` skill — a green cycle is not evidence of no findings.

Outcome: [verify verdict] · [review verdict] · [test count] — findings below are about the
pipeline, not the feature.

### P[0-3] — [short title]

[What happened and what it cost.]

**Evidence:** [report path / agent id / file:line / quoted agent return]
**Suggested fix:** [what would prevent a recurrence, or "unclear — needs triage"]

### What worked, and is worth keeping

- [Behaviour, and whether it should be promoted into an agent or skill definition]

(or `None — probes 1-12 checked, all clean.`)

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
- **Harness findings are separate from the metrics above.** The metrics answer how the work
  went; harness findings answer what the pipeline cost getting there. A cycle can be green on
  every metric and still have a P0 — see the `harness-findings` skill for why that is not
  hypothetical.
- **Agent Audit accuracy**: if you're unsure whether `model` was set on a spawn, record "uncertain" — do not guess "yes"

## Report archival

**Only when `vault_root` is empty** (§ Docs Vault in `.omp/agent-config.md`). If >10 reports in
`agent_tasks/reports/`, summarize the oldest into `agent_tasks/agent_metrics.md` (cumulative
metrics table) and delete the archived files.

**With a vault configured, never delete.** `agent_tasks/reports` is a symlink into a shared,
git-backed vault holding every application's history — one deployment is past 200 files, which
is the rule working as intended, not a backlog. The count threshold was written for a local
directory of a dozen reports and does not transfer.

Summarization is still worth doing there, so when the vault is set: append to
`agent_metrics.md` as usual and leave every report file in place. Do not treat a large report
count as a condition to act on.
