---
name: pipeline-metrics-rubric
description: The taxonomy of patterns self-improve looks for across run reports, the recommendation format, and the confidence × impact priority order. Single source of truth for pipeline-tuning analysis.
disable-model-invocation: true
---

# Pipeline Metrics Rubric

The self-improve agent reads run reports + verify audits and identifies recurring patterns. This skill defines what to look for, how to write recommendations, and how to prioritize them.

---

## Data to extract per report

### Economy
- Agent model usage per phase / task.
- Model escalations (cheaper model failed → retried with expensive).
- Possible downgrades (expensive model used on trivial task).

### Efficiency
- Rework cycles per parent task (count and cause).
- Blockers (count, cause).
- Parallelism utilization (parallel vs. serial tasks).
- Phase bottlenecks.

### Effectiveness
- Verify verdicts (PASS / WEAK / INCOMPLETE / NO TEST / NO IMPL).
- Test failures caught pre-commit.
- Skill gaps observed (from both run and verify reports).

---

## Patterns to look for (organized by 3Es)

### Economy patterns
- **Model allocation accuracy.** haiku fails >25% on a task type → upgrade. opus used on a task that never reworks → downgrade.
- **Pre-digestion effectiveness.** Are haiku digests reducing sonnet token usage?
- **Cost hotspots.** Which phases consume the most tokens?

### Efficiency patterns
- **Rework hotspots.** Which sub-task types cause the most rework? Model problem (upgrade) or agent-instruction problem (improve the agent)?
- **Blocker patterns.** PRD ambiguity? Task granularity? Implementation complexity?
- **Parallelism gaps.** Are independent tasks being serialized unnecessarily?

### Effectiveness patterns
- **Verify verdict trends.** Is PASS rate improving? Which verdict types are most common?
- **Skill gap themes.** Do the same gaps appear across runs? Group by agent.
- **Anti-faking performance.** Are WEAK verdicts decreasing?
- **Coverage gaps.** Are NO TEST verdicts concentrated in a specific layer?

### Supervisor health patterns (5.5.5 / 5.5.6)
- **Stall / disable frequency.** Tally `supervisor-stall` and `supervisor-disabled` rescue types across the last 5 cycles. ≥3 of 5 → **P0**.
- **Uptime trend.** Run-report Agent Telemetry: cycles flagged "degraded" (<90% uptime) recurring → P0.
- **Whisper precision (OQ-4 stub).** When agent return summaries include a "Whispers seen and response" line, sample and grade post-hoc. Feed grades back as a recommendation when a detector is consistently noisy.
- **Threshold tuning.** Detector firing `pause` (3-strike) in <5% of cycles → too lax (raise sensitivity). >50% → too aggressive (lower). Edit `.omp/agent-config.md` § Supervisor Thresholds.
- **Recommendation accept ratio.** Group `## Supervisor recommendations` rows by detector. Accept ratio <20% across last 5 cycles → noisy detector; adjust thresholds or disable.

### Mode + depth patterns (5.6.4 / 5.6.6)
- **Mode-suggestion accuracy.** Read each cycle's `Mode suggestion: ... | accepted: ...` field. Users override >40% of the time across last 5 cycles → propose adjusted keyword lists or word-count thresholds in `.claude/skills/cycle/SKILL.md` § Mode auto-suggestion.
- **Verify depth distribution + find-rate.** Group cycles by `Verify depth:`; compare verdict statistics. `lite` non-PASS rate higher than `standard` by ≥10pp → tighten lite predicate. `deep` never finds more than `standard` → loosen deep predicate.

---

### Harness finding patterns

Per-cycle process faults recorded under `## Harness findings` (taxonomy owned by the
`harness-findings` skill). Read them across reports, not within one.

- **Same finding in ≥3 of the last 5 cycles** — a pipeline defect, not an incident.
  Recommend at **high** confidence regardless of individual severity.
- **Any P0, even once** — recommend immediately. "Agents built against the wrong base"
  does not need a second occurrence to be worth fixing.
- **A probe that never reports anything across many cycles** — either genuinely clean or
  never actually checked. Cross-check against reports that wrote `None`; a run report with
  a `RESCUE` line and no findings is a signal the checklist was skipped.
- **Repeated "what worked" entries** — a behaviour being re-requested per prompt each
  cycle belongs in an agent or skill definition. Recommend promoting it.

## Recommendation format

```markdown
### [REC-001] [Short title]

**Change**: Which file and section to edit, and what to change.

**Evidence**: Which reports support this. Cite specific run reports and metrics.

**Expected impact**:
- Economy / Efficiency / Effectiveness: [estimate]

**Risk**: What could go wrong.

**Confidence**: high / medium / low (based on sample size and consistency)
```

---

## Priority order

1. **High confidence + high impact** — apply these.
2. **High confidence + low impact** — apply these (easy wins).
3. **Low confidence + high impact** — flag for monitoring, do not apply yet.
4. **Low confidence + low impact** — skip.

Apply levels 1 and 2 without waiting for user input. Levels 3 and 4 are listed in the report but not applied.

---

## Edge cases

- **Single run report**: flag most recommendations as "needs more data" unless the pattern is unambiguous (e.g., 100% failure rate on a task type).
- **No run reports**: report that self-improve needs data from at least one cycle run.
- **Contradictory data**: dig into cause (task complexity, PRD quality, codebase area). Recommend monitoring rather than changing.
- **No verify data**: economy and efficiency analysis can proceed; effectiveness analysis will be limited.
