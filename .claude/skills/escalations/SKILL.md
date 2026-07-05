---
name: escalations
description: Escalation channel spec — how the Phase-3 supervisor signals the orchestrator via append-only JSONL, and when the orchestrator polls. Synthesis item 5.5.2.
disable-model-invocation: true
---

# Escalations

The Phase-3 supervisor signals the orchestrator via **escalations** — structured JSON lines appended to `agent_states/escalations.jsonl`. Unlike whispers, escalations are *orchestrator-directed* and may carry binding requests.

This skill defines the line schema and the orchestrator's polling cadence.

---

## File format

One file per cycle: `agent_states/escalations.jsonl`. Append-only. One JSON object per line. Newer at the bottom.

### Common fields (every line)

```json
{
  "ts": "2026-05-22T14:35:01Z",
  "type": "pause-request | depth-recommendation | bug-pattern",
  "agent_id": "<role>-<task-number> or null if cycle-wide",
  "detector": "spiral | drift | stall | shallow | contradiction | null"
}
```

### Type-specific fields

**`pause-request`** — paired with a `pause` whisper. Asks the orchestrator to take action because the agent is now stopped.
```json
{
  ...,
  "type": "pause-request",
  "reason": "spiral detector: 3 consecutive edits failed analyze",
  "events_seen": ["edit:lib/foo.dart", "edit:lib/foo.dart", "edit:lib/foo.dart"],
  "recommendation": "escalate to L3 (opus fresh attempt) or surface to user"
}
```

**`depth-recommendation`** — non-binding suggestion that the orchestrator change pipeline depth (e.g., add a verify pass, switch the agent's model, split the task). Orchestrator records the decision either way (accepted or rejected with rationale) — see 5.5.6.
```json
{
  ...,
  "type": "depth-recommendation",
  "suggestion": "split task 2.0 — sub-tasks 2.4 and 2.5 are independent of the rest",
  "evidence": "no tool calls reference shared symbols across 2.3↔2.4"
}
```

**`bug-pattern`** — informational. The supervisor noticed a pattern across multiple agents that the run report should capture (e.g., everyone's missing a `setUpAll` for `registerFallbackValue`). No action required from the orchestrator beyond logging.
```json
{
  ...,
  "type": "bug-pattern",
  "pattern": "registerFallbackValue missing for enum X across 3 test files",
  "agent_ids_affected": ["test-1.0", "test-2.0", "test-3.0"]
}
```

---

## Orchestrator polling cadence

The orchestrator polls `escalations.jsonl` at **three moments only**:

1. **Phase transition** — end of Phase 3 → before spawning verify/review.
2. **Sub-task boundary** — after each parent task's Commit protocol completes (and before spawning the next dependent task).
3. **Watchdog tick** — whenever the orchestrator runs its periodic watchdog (currently aligned to monitor health check + supervisor heartbeat check from 5.5.5).

The orchestrator does **not** poll mid-tool-call. Up-to-30s latency on `pause-request` is acceptable; the alternative defeats sidecar separation. If you (as supervisor) need faster response, the synthesis plan says: reconsider the architecture, don't tighten the poll.

---

## Polling implementation

When the orchestrator polls:

1. **Read** `agent_states/escalations.jsonl` from a per-cycle cursor (track in cycle state under a new `escalation_cursor:` field; first poll starts at line 1).
2. **Process each unread line:**
   - `pause-request` → if the named agent's most recent state is in-progress, treat as a stalled-agent signal: trigger Stall salvage or jump to escalation ladder L4. The matching `pause` whisper has already stopped the agent; your job is the recovery decision.
   - `depth-recommendation` → log to cycle state under `## Supervisor recommendations` with `accepted: true|false` and `rationale: …`. Apply if accepted.
   - `bug-pattern` → log to cycle state under `## Bug patterns`; surface in the run report.
3. **Advance cursor** to the last line processed.

---

## What escalations do NOT do

- They do not pause agents (that's a `pause` whisper's job, paired with a `pause-request` escalation).
- They do not bypass the orchestrator's normal escalation ladder for unrelated failures; they only request the orchestrator's attention on supervisor-detected conditions.
- They are not retried. If the orchestrator ignores or misses an escalation, the supervisor does not re-emit it — the next check produces a fresh line if the condition persists.

---

## Layering with rescues

When the orchestrator processes a `pause-request` and decides on a recovery path, it emits a corresponding `RESCUE` event to monitor (per the existing 5.2.3 plumbing). The escalation captures *what the supervisor saw*; the rescue captures *what the orchestrator did about it*. Both flow into the run report.

## OMP IRC transport (default under omp)

Under omp, escalations travel over the **irc** tool instead of `agent_states/escalations.jsonl`.
The supervisor sends directly to the orchestrator:

```
irc(op: "send", to: "Main", message: "<type> | agent: <id> | detector: <name> | <type-specific fields>")
```

The three types (`pause-request`, `depth-recommendation`, `bug-pattern`) keep the same
field shape, serialized as a single-line pipe-delimited message body. The orchestrator
parses the prefix to decide the action.

### Orchestrator receipt (replaces polling)

The orchestrator no longer polls `escalations.jsonl` at 3 moments. Instead, at each of those
moments (phase transition, sub-task boundary, watchdog tick) it drains its irc inbox:

```
irc(op: "inbox")   # non-blocking drain; returns all pending escalation messages
```

For time-sensitive `pause-request` handling, the orchestrator can `wait` with a bounded
timeout at watchdog ticks:

```
irc(op: "wait", from: "supervisor-<tick>", timeoutMs: 30000)
```

The cursor tracking (`escalation_cursor:` in cycle state) is unnecessary under irc — messages
are consumed on read, not seeked by line number.

### Pairing with whispers

`pause-request` escalations still pair with `pause` whispers. Under irc, both travel as irc
sends in the same supervisor check: the whisper to the implementation agent, the escalation to
the orchestrator.

### Audit trail

File-path escalations archive to `cycle_reports/<feature>/supervisor/escalations.jsonl`.
Under irc, the audit trail is the orchestrator's session JSONL. The supervisor echoes every
escalation to its own return summary so the run report aggregates them.

### When to fall back to the file path

The file path is the Claude Code fallback. Under omp, irc is the default.
