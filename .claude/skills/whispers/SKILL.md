---
name: whispers
description: Whisper channel spec — the Phase-3 supervisor advises implementation agents, and how agents respond. Transport is omp irc; file path is the Claude Code fallback. Synthesis item 5.5.2.
disable-model-invocation: true
---

# Whispers

The Phase-3 supervisor emits **whispers** — short, agent-directed advisories — to implementation agents (test, ui-story, scaffold, coding). Under omp, whispers travel over the **irc** tool: delivered immediately at the recipient's next step boundary, no polling. The severity ladder and compliance rules below are transport-agnostic.

## Transport (omp irc — default)

Supervisor → implementation agent:

```
irc(op: "send", to: "<agent-id>", message: "[<severity>] <detector>: <body>")
```

- `severity` — `note` | `strong` | `pause` (the ladder below).
- `detector` — `spiral` | `drift` | `stall` | `shallow` | `contradiction`.
- `body` — one paragraph citing the specific event (file path, tool call, AC reference).

The recipient receives the message as an `irc:incoming` turn at its next step boundary. No polling, no cursor.

## Severity semantics

- **`note`** — advisory. The supervisor sees something worth flagging but has low confidence the agent should change course. Agents *may* ignore; they have context the supervisor lacks. Common case: a `shallow` detector hit on the first edit of a long task.
- **`strong`** — also advisory, higher confidence. The supervisor is seeing a pattern persist across multiple checks. Agents *should* read and respond, but may still continue if their context warrants. Common case: `spiral` detector firing twice in a row.
- **`pause`** — binding. The agent must stop further tool calls, write a brief status (`paused: waiting on orchestrator`), and exit the sub-task. The orchestrator will follow up after receiving a matching `pause-request` escalation (see `escalations` skill). Common case: `stall` or `contradiction` after escalation-ladder step 3.

Severity rises monotonically across the ladder (5.5.4): first detection → `note`; persists → `strong`; still persists → `pause` (with matching `pause-request` escalation).

## Agent receipt + compliance

When a whisper arrives, apply the severity rule:

- `note` — note it; act if you agree with the assessment after reading the body.
- `strong` — read carefully; default action is to apply the recommendation unless you can justify ignoring it in your final report.
- `pause` — stop. Write `paused: waiting on orchestrator (whisper ts: <ts>, detector: <name>)` to your spawn output. Do not start the next sub-task.

**Log compliance** — in your final return summary, list the whispers you saw and your response: ignored / followed / paused. Verify reads this to audit whether whispers changed behavior.

You do not whisper to yourself. Only the supervisor sends whispers.

## What whispers do NOT do

- They do not block tool calls mid-execution. irc delivers at the next step boundary, not mid-tool-call.
- They do not replace the orchestrator's escalation ladder. Whispers are agent-directed; the orchestrator's ladder is task-directed.
- They do not carry binding *plan changes*. If the supervisor wants the orchestrator to revise depth or pipeline, it sends an escalation (see `escalations` skill), not a whisper.

## Supervisor-side rules

- One whisper per detector firing — don't batch.
- Body cites a specific event (tool call, file, AC). Vague bodies ("you might be stuck") are worthless.
- For `pause` whispers, you must *also* send a matching `pause-request` escalation to the orchestrator in the same check — they travel as a pair.
- Never whisper to an agent that hasn't appeared in `events/` yet (the agent doesn't exist, you're hallucinating an ID).
- Echo every whisper you send to your own return summary so the run report aggregates them in one place.

## Claude Code fallback (file path)

When irc is unavailable (Claude Code), the supervisor appends whispers to `agent_states/whispers/<agent-id>.md` — one YAML-frontmatter block per whisper (`ts`, `severity`, `detector`) followed by a prose body. Implementation agents poll this file between sub-tasks, scanning from their last cursor. The directory archives to `cycle_reports/<feature>/supervisor/whispers/` at cycle end. Under omp, this path is unused.
