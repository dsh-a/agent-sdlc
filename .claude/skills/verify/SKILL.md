---
name: verify
description: Independent acceptance criteria coverage audit. Delegates to the verify agent to evaluate whether the implementation and test suite genuinely satisfy the PRD's acceptance criteria. Complements review (which focuses on code quality).
disable-model-invocation: true
---
# Verify

User-facing shim for the `verify` agent. The agent owns the independent AC audit; this skill is what `/verify` invokes.

The PRD or feature to verify: **$ARGUMENTS**

---

## What to do

1. If `$ARGUMENTS` is empty, ask the user which PRD or feature to verify. Search `agent_tasks/` for matching PRD files if a name is partial.

2. Resolve inputs:
   - **PRD path** — required. Ask if missing.
   - **Branch** — default to the current branch (`git branch --show-current`); confirm with user if it doesn't look feature-shaped.
   - **Depth** — ask the user: `lite | standard | deep`. If they don't know, default to `standard`. Cycle-orchestrator depth selection (5.6.6) does not apply here — this is a user-driven run.

3. Spawn the `verify` agent:

```
Agent(subagent_type: "verify", model: "sonnet",
      prompt: "PRD: [path]. Branch: [name]. Depth: [tier].
               Report path: agent_tasks/reports/verify-[prd-stem]-[date].md.
               Work autonomously — no user interaction.")
```

4. After completion, read the report file and present its Coverage Matrix, Summary Statistics, and Recommendations to the user.

5. If the report verdict is `FAIL` or `PARTIAL`, ask the user what to do (open follow-up tasks, edit AC, accept the partial verdict).

---

## What this shim does NOT do

- Re-implement the audit steps. The agent owns Steps 0a / 0 / 1–10 with the `ac-audit-rubric` skill loaded.
- Modify source or test files. Verify is read-only by design.
- Decide cycle-level depth — that's the orchestrator's job in `/cycle`'s Phase 4A.
