---
name: contradiction-exit
description: Structured halt-and-report signal an agent emits when it encounters incompatible sources of truth and cannot make further progress without human judgment. Generalized from synthesis item 5.4.4; consumed today only by the test agent but designed as a primitive any agent can adopt.
disable-model-invocation: true
---

# Contradiction Exit

When you — the calling agent — encounter two or more incompatible sources of truth and continuing would either lock in wrong behavior or thrash, **halt and emit this structured signal** in your final report. Do not silently pick a side. Do not retry past the cap your own flow defines.

The orchestrator treats this signal as L4 (block and surface to user). Auto-retry on contradiction-exit is wrong by construction — you've already attempted whatever was attemptable.

---

## When to emit

Emit `contradiction-exit` when any pair of these is mutually unsatisfiable:

- **AC vs. AC** — two acceptance criteria in the same PRD contradict each other.
- **AC vs. impl** — the AC requires behavior X, the implementation does Y, and your task scope does not include changing the implementation.
- **AC vs. existing test** — the AC requires behavior X, an existing test asserts Y, and you cannot satisfy both.
- **AC vs. interface** — the AC requires a behavior the public interface cannot express (return type, parameter shape).
- **Rubric vs. impl** — a rubric check (5.4.1) keeps failing after the retry cap because the impl makes the check unsatisfiable.
- **Pre-flight vs. AC** — a pre-flight classification (5.4.3) marks a test for deletion, but the test asserts a *different* AC the PRD still requires.

**Do not emit** for:
- Missing context you could fetch (read the file, search the codebase).
- Single failures that haven't exhausted the retry cap.
- Disagreement with a prior agent — that's a `deviation:`, not a contradiction (see 5.3.3).
- Ambiguity you can resolve by reading the PRD more carefully.

---

## Required block

Include this block verbatim in your final return value. The orchestrator parses it mechanically.

```
status: contradiction-exit
trigger: [enum: ac-vs-ac | ac-vs-impl | ac-vs-existing-test | ac-vs-interface | rubric-vs-impl | preflight-vs-ac | other]
sources:
  - [first source — file:line, AC #, test name, etc.]
  - [second source — same shape]
detail: [one paragraph explaining why these two sources cannot both be satisfied within your task scope]
attempted: [what you tried before emitting — e.g., "Rewrote test twice, both iterations failed rubric check #3 because impl rejects all inputs."]
recommendation: [what a human should decide — "AC #3 needs revision", "impl task is missing from this PRD", "test infrastructure missing fake clock", etc.]
```

If your agent's own protocol defines additional fields (e.g., `rubric_check` and `iterations` from the test-rubric flow), append them after `recommendation:` — the orchestrator preserves unknown fields when forwarding to monitor.

---

## What the orchestrator does

On detecting `status: contradiction-exit` in your return:

1. Emits `RESCUE contradiction-loop [task-id]: [trigger] | resolution: human escalation | artifact: [report path]` to monitor.
2. Skips L1–L3 of the escalation ladder. Goes directly to **L4** (block, surface to user). Auto-retry is disabled for this specific failure mode.
3. The structured block is preserved verbatim in the user-facing message — you set the framing, not the orchestrator.

---

## Layering with related improvements

- **5.4.1 (rubric)** — defines the rubric-retry loop that emits `rubric-vs-impl` exits.
- **5.4.3 (pre-flight)** — produces classifications that can cause `preflight-vs-ac` exits.
- **5.3.3 (deviations)** — for the *non-contradiction* case where you proceeded but diverged from PRD intent; emit a deviation, not an exit.
- **Stall salvage** — for cases where you couldn't return *any* result. Contradiction-exit is for when you returned a result that says "I can't make progress."
