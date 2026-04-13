# Self-Improve — Pipeline Performance Analysis

You are analyzing the performance of the development pipeline to identify concrete improvements. You read historical run reports and /verify audits, find patterns, and propose specific edits to skills and configuration.

**$ARGUMENTS** can be:
- Empty: analyze all reports in `agent_tasks/reports/`
- A specific report path: analyze just that run
- A dimension: `economy`, `efficiency`, or `effectiveness` — focus analysis on that dimension

---

## Step 1 — Gather data

Read all files in `agent_tasks/reports/`. For each report, extract:

### Economy data
- Agent model usage per phase/task
- Model escalations (cheaper model failed → retried with expensive)
- Possible downgrades (expensive model used on trivial task)
- Estimated token usage per agent

### Efficiency data
- Rework cycles per parent task (count and cause)
- Blockers (count, cause, resolution time impact)
- Parallelism utilization (how many tasks ran in parallel vs. serial)
- Phases that took disproportionately long

### Effectiveness data
- /verify verdicts (PASS, WEAK, INCOMPLETE, NO TEST, NO IMPL)
- Test failures caught pre-commit
- Skill gaps observed (from both run reports and verify reports)
- Commits that required reattempt

---

## Step 2 — Analyze patterns

Look across multiple runs for recurring patterns. Organize findings by the 3Es:

### Economy patterns
- **Model allocation accuracy**: Is the model table in `/cycle` well-calibrated?
  - If haiku fails >25% of the time on a task type → recommend upgrading
  - If opus is used on a task type that never has rework → recommend downgrading
  - If a task type has mixed results → recommend keeping current model but note it
- **Pre-digestion effectiveness**: Are haiku digests reducing tokens on expensive agents? Are there phases where pre-digestion isn't being used but should be?
- **Cost hotspots**: Which phases consume the most tokens? Are there structural changes that could reduce this?

### Efficiency patterns
- **Rework hotspots**: Which sub-task types cause the most rework? Is it a model problem (upgrade) or a skill problem (better instructions)?
- **Blocker patterns**: Are blockers caused by PRD ambiguity (improve /create-prd), task granularity (improve /generate-tasks), or implementation complexity (improve /scaffold or /test)?
- **Parallelism gaps**: Are independent tasks being serialized unnecessarily? Is the dependency analysis in Phase 3.1 missing opportunities?
- **Phase bottlenecks**: Is one phase consistently slower than others?

### Effectiveness patterns
- **Verify verdict trends**: Is the PASS rate improving over time? Which verdict types are most common?
- **Skill gap themes**: Do the same gaps appear across runs? Group them by skill.
- **Anti-faking performance**: Are WEAK verdicts decreasing? If not, the /test skill's anti-faking checks need strengthening.
- **Coverage gaps**: Are NO TEST verdicts concentrated in a specific area (UI, domain, data layer)?

---

## Step 3 — Generate recommendations

For each finding, produce a specific, actionable recommendation. Each recommendation must include:

1. **What to change** — the specific skill file and section to edit
2. **Evidence** — which reports and metrics support this change
3. **Expected impact** — which E(s) this improves and by how much (estimate)
4. **Risk** — what could go wrong if this change is wrong
5. **Confidence** — high/medium/low based on sample size and consistency

### Recommendation format

```
### [REC-001] Upgrade scaffold tasks from haiku to sonnet

**Change**: In `.claude/skills/cycle.md`, model allocation table, change
scaffold row from `haiku` to `sonnet`.

**Evidence**: Across 4 runs, haiku scaffold failed 3/8 times (37.5%).
Failures were all related to complex generic type resolution. Sonnet
succeeded on retry in all 3 cases with no rework.
- report-login-2026-03-15.md: task 1.2 escalated
- report-settings-2026-03-22.md: tasks 1.1, 2.3 escalated

**Expected impact**:
- Economy: +$0.02/run (sonnet vs haiku for ~8k tokens)
- Efficiency: -1.5 rework cycles/run (eliminates retry overhead)
- Net: positive — retry costs more than the model upgrade

**Risk**: Low. Sonnet handles all scaffold tasks; no observed failures.

**Confidence**: High (consistent pattern across 4 runs)
```

### Priority

Rank recommendations by:
1. **High confidence + high impact** — do these first
2. **High confidence + low impact** — easy wins
3. **Low confidence + high impact** — needs more data, flag for monitoring
4. **Low confidence + low impact** — skip

---

## Step 4 — Present findings

Present the analysis in three sections matching the 3Es, followed by ranked recommendations.

### Report structure

```
## Economy Summary
[Key findings about cost, model usage, token efficiency]
[Trend over time if multiple reports]

## Efficiency Summary
[Key findings about rework, blockers, parallelism, bottlenecks]
[Trend over time if multiple reports]

## Effectiveness Summary
[Key findings about quality, verify pass rates, skill gaps]
[Trend over time if multiple reports]

## Recommendations (ranked)
[REC-001] ...
[REC-002] ...
...

## Monitoring — Items needing more data
[Patterns observed but not yet confident enough to act on]
```

Ask the user: **"Which recommendations would you like me to apply?"**

---

## Step 5 — Apply approved changes

For each approved recommendation:

1. Read the target skill file
2. Make the specific edit described in the recommendation
3. Show the diff to the user for confirmation
4. Save the change

After all changes are applied, add a note to the most recent run report:

```
## Self-improve applied [YYYY-MM-DD]
- [REC-001] Upgraded scaffold from haiku to sonnet
- [REC-003] Added verifyNever guidance to /test skill
```

This creates an audit trail so future `/self-improve` runs can assess whether the changes helped.

---

## Edge cases

- **Single run report**: Analysis is possible but confidence will be low for most recommendations. Flag everything as "needs more data" unless the pattern is unambiguous (e.g., 100% failure rate on a task type).
- **No run reports**: Inform the user that `/self-improve` needs data from at least one `/cycle` run. Suggest running `/cycle` first.
- **Contradictory data**: If a model works well in some runs and fails in others, dig deeper — is it the task complexity, the PRD quality, or the codebase area? Recommend monitoring rather than changing.
- **No /verify data**: Economy and efficiency analysis can proceed, but effectiveness analysis will be limited. Recommend running `/verify` on past features to backfill data.
