---
name: self-improve
description: Analyze past cycle runs and tune agent/skill instructions. Extracts patterns from run reports, proposes improvements to agent prompts, skill files, and pipeline thresholds. Supports scoping by economy, effectiveness, or specific report.
disable-model-invocation: true
---
# Self-Improve

User-facing shim for the `self-improve` agent. The agent owns the pipeline-tuning analysis; this skill is what `/self-improve` invokes.

Optional scope filter: **$ARGUMENTS** (e.g., `economy`, `effectiveness`, a specific report path, or a `REC-NNN` to apply)

---

## What to do

1. Check that `agent_tasks/reports/` exists and contains at least one run report. If empty, tell the user no data is available and stop — self-improve needs cycle data.

2. Spawn the `self-improve` agent with the scope (or empty for all):

```
spawn agent: self-improve
    Scope: [argument or 'all'].
```

3. Surface the agent's report sections to the user:
   - Economy / Efficiency / Effectiveness summaries.
   - Recommendations Applied (high-confidence).
   - Recommendations Not Applied (low-confidence — needs more data).
   - Monitoring — items needing more data.

4. If high-confidence recommendations were applied, ask the user whether to commit them. The agent makes edits but does not commit.

---

## What this shim does NOT do

- Re-implement the pattern analysis. The agent applies `pipeline-metrics-rubric` automatically — data taxonomy, full pattern library across 3Es + supervisor health + mode/depth, recommendation format, priority order, edge cases.
- Roll back applied changes. If the user rejects a recommendation, surface the file the agent touched so they can revert manually.
