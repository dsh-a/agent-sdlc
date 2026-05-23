# Write Tests

User-facing shim for the `test` agent. The agent owns the rigorous, anti-faking test-writing workflow; this skill is what `/test` invokes.

The class or feature to test: **$ARGUMENTS**

---

## What to do

1. If `$ARGUMENTS` is empty, ask the user what class, method, or feature to test.

2. Determine context:
   - **PRD-driven** — if a PRD or story exists in `agent_tasks/`, find the matching file and extract its AC. If you can't find one, ask the user for the AC inline before proceeding.
   - **Code-driven** — if no PRD exists and the user can't supply AC, derive from the source's public API and existing behavior, and flag in the report that no PRD was used.

3. Spawn the `test` agent with the gathered context:

```
Agent(subagent_type: "test", model: "sonnet",
      prompt: "Source files: [paths]
               Test files: [paths or 'derive from source path']
               AC: [pre-extracted from PRD or supplied inline]
               Task: write tests for [target]")
```

4. Surface the agent's report (test files written/modified, AC coverage, rubric outcome, items requiring user action) verbatim.

5. If the agent returned a `contradiction-exit` block, present it to the user verbatim and ask how to proceed — do not retry automatically.

---

## What this shim does NOT do

- Re-implement the test workflow inline. The agent owns Steps 1–7 (gather AC, read source, check existing tests + pattern, plan, write, run + rubric, report). Loading the agent gives you `flutter-conventions`, `widget-test-patterns`, `test-rubric`, `contradiction-exit`, `pattern-divergence`, and `whispers` skills automatically.
- Apply rubric checks itself. The agent does that in-process.
- Decide depth tiering. That's a cycle-orchestrator decision (5.6.6), not a `/test` concern.
