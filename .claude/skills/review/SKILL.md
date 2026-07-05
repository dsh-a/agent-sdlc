---
disable-model-invocation: true
---

# Review

User-facing shim for the `review` agent. The agent owns the independent code review; this skill is what `/review` invokes.

The branch or PR to review: **$ARGUMENTS**

---

## What to do

1. Resolve target:
   - If `$ARGUMENTS` looks like a PR number (`#123` or `123`) → use `gh pr diff [number]` as the changeset source.
   - If a branch name → use `git diff [base]...[branch]` (read `base` from `.claude/config.md` § Branch Configuration; default `main`).
   - If empty → default to the current branch; confirm with the user.

2. Spawn the `review` agent:

```
Agent(subagent_type: "review", model: "sonnet",
      prompt: "Branch: [name or PR ref]. PRD: [path or 'none'].
               Report path: agent_tasks/reports/review-[feature]-[date].md.
               Work autonomously — no user interaction.")
```

3. After completion, read the report file and present:
   - Verdict (APPROVE / REQUEST CHANGES / NEEDS DISCUSSION).
   - Critical and Warning counts (fixed vs. remaining).
   - The Auto-Fixed Issues section so the user can see what changed.

4. If the verdict is `REQUEST CHANGES`, list the remaining critical findings inline and ask the user how to proceed.

---

## What this shim does NOT do

- Re-implement the review steps. The agent owns Steps 0–7 with `project-conventions` and `review-report-format` skills loaded.
- Apply non-critical fixes. The agent auto-applies Critical + Warning per `review-report-format`; Suggestions are listed only.
