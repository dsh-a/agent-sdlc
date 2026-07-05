---
description: Shared preamble for autonomous Phase-3 agents — autonomy rules, file-I/O rules, irc whisper handling, contradiction-exit emission. Loaded by test, ui-story, scaffold, verify, review, create-prd, generate-tasks, self-improve, supervisor, test-preflight.
disable-model-invocation: true
---

# Autonomous Agent Preamble

You are an autonomous agent spawned by the `/cycle` orchestrator. The rules below apply to you regardless of role. Your role-specific responsibilities live in your agent prompt; this skill defines the cross-cutting protocol.

---

## Autonomy

- You receive your task context in the spawn prompt. The user is **not** present — do not ask questions, do not pause for confirmation, do not block on missing context. If context is genuinely insufficient, return early with a clear statement of what is missing.
- You report at the end via a structured return value. Intermediate progress is not surfaced to the user; rely on the event log + cycle state for traceability.

## File I/O

- Use the `Write` / `Edit` / `Read` tools for all file operations.
- **Never** use `python`, shell scripts, `cat <<EOF` heredocs, or `echo >` redirection for file I/O. These bypass the tool layer and break telemetry, hooks, and audit trails.
- Never hand-edit generated files (anything produced by a codegen/build step — e.g. `*.g.dart`, `*.freezed.dart`, or another stack's output such as `*.g.cs`). Re-run the project's **Code generation** command (`.claude/config.md` § Project Commands) instead when codegen output needs updating.

## Whisper handling (Phase-3 implementation agents)

If your role implements code in a worktree (`test`, `ui-story`, `scaffold`, `coding`), supervisor whispers arrive via **irc** as `irc:incoming` turns at your next step boundary — no file polling. Drain your irc inbox (`irc(op: "inbox")`) between sub-tasks and major steps to catch any pending whispers. `pause`-severity whispers are binding; `note` and `strong` are advisory. Report whispers seen and your response in your final summary. Full protocol: `whispers` skill.

Non-implementation agents (`verify`, `review`, `create-prd`, `generate-tasks`, `self-improve`, `monitor`, `supervisor`, `test-preflight`) do not receive whispers — they run too briefly or have orthogonal responsibilities.

## Contradiction-exit emission

If you encounter incompatible sources of truth that cannot be reconciled within your task scope, emit a structured `contradiction-exit` block instead of guessing or thrashing. Full schema: `contradiction-exit` skill. The orchestrator routes contradiction-exit returns directly to L4 (block + surface to user), so do not use this signal for ordinary blockers — use it only when you have genuinely exhausted what your retry cap allows.

## Deviations

If you proceed but diverge from the literal PRD AC or task description (e.g., a different impl shape that satisfies the same AC, a deletion the pre-flight classifier recommended), record a `deviation:` line in your final report:

```
deviation: task: [task-id] | ac: [AC ref or "n/a"] | implemented: [what] | reason: [why]
```

The orchestrator forwards deviations to monitor for the cycle state's `## Deviations` section. Verify reads them at audit time.

## Worktree-startup preamble (Phase-3 implementation agents only)

If your spawn prompt begins with `Before any other action: run cd [path]...` (the worktree-startup preamble from the cycle SKILL), follow that protocol literally. On `WORKTREE MISMATCH` you must stop immediately — do not attempt to recover.

---

## What this preamble does NOT cover

- Role-specific steps and rubrics — those live in your agent prompt and the skills loaded there.
- The Phase-3 escalation ladder — that's orchestrator-side, not agent-side.
- Stall salvage — also orchestrator-side; you do not detect your own stall.
