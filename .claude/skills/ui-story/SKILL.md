# UI Story

User-facing shim for the `ui-story` agent. The agent owns the UI implementation workflow; this skill is what `/ui-story` invokes.

The screen, component, or feature: **$ARGUMENTS**

---

## What to do

1. If `$ARGUMENTS` is empty, ask the user what to build.

2. Resolve context:
   - **PRD or task** — if the work is PRD-driven, locate the file in `agent_tasks/`. If the user is making something one-off, ask for AC inline.
   - **Existing code** — confirm whether the ViewModel/View already exists or needs creation.

3. Spawn the `ui-story` agent:

```
Agent(subagent_type: "ui-story", model: "sonnet",
      prompt: "PRD: [path or 'inline AC: ...'].
               Source files: [paths or 'derive'].
               AC: [pre-extracted].
               Task: [description].")
```

4. Surface the agent's report: files created/modified, DI + route wiring added, AC coverage, test file path + count, golden update commands (if any), analyze/test status.

5. If the agent flagged items it could not implement, ask the user how to proceed.

---

## What this shim does NOT do

- Re-implement Step 1–8. The agent owns the workflow with `project-conventions`, `ui-test-patterns`, `whispers`, and `scaffold` skills loaded.
- Decide presentation-layer conventions. The agent reads `project-conventions` and project overrides in `.claude/config.md` automatically.
