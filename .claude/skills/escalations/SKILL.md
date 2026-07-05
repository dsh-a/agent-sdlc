---
name: escalations
description: Escalation channel spec — the Phase-3 supervisor signals the orchestrator. Transport is omp irc; JSONL file is the Claude Code fallback. Synthesis item 5.5.2.
disable-model-invocation: true
---

# Escalations

The Phase-3 supervisor signals the orchestrator via **escalations** — structured, orchestrator-directed messages that may carry binding requests. Under omp, escalations travel over the **irc** tool. Unlike whispers, escalations are orchestrator-directed.

## Transport (omp irc — default)

Supervisor → orchestrator:

```
irc(op: "send", to: "Main", message: "<type> | agent: <id> | detector: <name> | <type-specific fields>")
```

The orchestrator drains its irc inbox at three moments (no cursor — messages are consumed on read):

```
irc(op: "inbox")   # non-blocking drain at phase transition / sub-task boundary / watchdog tick
```

For time-sensitive `pause-request` handling at watchdog ticks:

```
irc(op: "wait", from: "supervisor-<tick>", timeoutMs: 30000)
```

## Three types

**`pause-request`** — paired with a `pause` whisper. Asks the orchestrator to take action because the agent is now stopped.
```
pause-request | agent: test-2.1 | detector: spiral | reason: 3 consecutive edits failed analyze | events_seen: edit:lib/foo.dart x3 | recommendation: escalate to L3 (opus fresh attempt) or surface to user
```

**`depth-recommendation`** — non-binding suggestion to change pipeline depth (add a verify pass, switch model, split task). Orchestrator records the decision either way (accepted or rejected with rationale — 5.5.6).
```
depth-recommendation | agent: 2.0 | detector: null | suggestion: split task 2.0 — sub-tasks 2.4 and 2.5 are independent | evidence: no shared symbols across 2.3↔2.4
```

**`bug-pattern`** — informational. A pattern across multiple agents the run report should capture. No action required beyond logging.
```
bug-pattern | agent: null | detector: null | pattern: registerFallbackValue missing for enum X across 3 test files | agent_ids_affected: test-1.0, test-2.0, test-3.0
```

## Orchestrator collection (3 moments)

1. **Phase transition** — end of Phase 3, before spawning verify/review.
2. **Sub-task boundary** — after each parent task's Commit protocol, before spawning the next.
3. **After each supervisor check** — drain any escalations the check emitted.

Process each drained message:
- `pause-request` → if the named agent is in-progress, trigger Stall salvage or jump to escalation ladder L4. The matching `pause` whisper already stopped the agent; your job is the recovery decision.
- `depth-recommendation` → log to cycle state `## Supervisor recommendations` with `accepted: true|false` and `rationale`. Apply if accepted.
- `bug-pattern` → log to cycle state `## Bug patterns`; surface in the run report.

Never block mid-tool-call. Up-to-30s latency on `pause-request` is acceptable; the alternative defeats sidecar separation.

## What escalations do NOT do

- They do not pause agents (that's a `pause` whisper's job, paired with a `pause-request`).
- They do not bypass the orchestrator's normal escalation ladder for unrelated failures; they only request attention on supervisor-detected conditions.
- They are not retried. If the orchestrator misses one, the supervisor does not re-emit — the next check produces a fresh message if the condition persists.

## Layering with rescues

When the orchestrator processes a `pause-request` and decides a recovery path, it emits a `RESCUE` event to monitor (5.2.3). The escalation captures *what the supervisor saw*; the rescue captures *what the orchestrator did*. Both flow into the run report.

## Audit trail

Under irc, the audit trail is the orchestrator's session JSONL. The supervisor echoes every escalation to its own return summary so the run report aggregates them.

## Claude Code fallback (file path)

When irc is unavailable (Claude Code), the supervisor appends JSON objects to `agent_states/escalations.jsonl` (one per line, fields: `ts`, `type`, `agent_id`, `detector`, plus type-specific fields). The orchestrator polls from a per-cycle `escalation_cursor:` in cycle state. The file archives to `cycle_reports/<feature>/supervisor/escalations.jsonl` at cycle end. Under omp, this path is unused.
