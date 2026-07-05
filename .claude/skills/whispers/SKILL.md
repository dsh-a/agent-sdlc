---
name: whispers
description: Whisper channel spec — how the Phase-3 supervisor advises an implementation agent via append-only files, and how the agent polls and responds. Synthesis item 5.5.2.
disable-model-invocation: true
---

# Whispers

The Phase-3 supervisor emits **whispers** — short, agent-directed advisories — to `agent_states/whispers/<agent-id>.md`. Implementation agents (test, ui-story, scaffold, coding, general-purpose) poll this file between sub-tasks. This skill defines the file format, severity semantics, and polling protocol.

You will be reading or writing whispers depending on your role. The format and rules are the same in both directions.

---

## File format

One append-only Markdown file per agent ID. Each whisper is a YAML-frontmatter block followed by a prose body. Multiple whispers concatenated.

```
---
ts: 2026-05-22T14:35:01Z
severity: note | strong | pause
detector: spiral | drift | stall | shallow | contradiction
---
Body: corrective note in prose. One paragraph. Cite the specific events or
state that triggered the whisper (file path, tool call, AC reference).
```

Newer whispers append to the bottom. Never rewrite or delete prior whispers — the file is the audit trail.

---

## Severity semantics

- **`note`** — advisory. The supervisor sees something worth flagging but has low confidence the agent should change course. Agents *may* ignore; they have context the supervisor lacks. Common case: a `shallow` detector hit on the first edit of a long task.
- **`strong`** — also advisory, higher confidence. The supervisor is seeing a pattern persist across multiple checks. Agents *should* read and respond, but may still continue if their context warrants. Common case: `spiral` detector firing twice in a row.
- **`pause`** — binding. The agent must stop further tool calls, write a brief status (`paused: waiting on orchestrator`), and exit the sub-task. The orchestrator will follow up with instructions (likely after receiving a matching `pause-request` escalation). Common case: `stall` or `contradiction` after escalation-ladder step 3.

Severity rises monotonically across the ladder defined in 5.5.4: first detection → `note`; persists → `strong`; still persists → `pause` (with matching `pause-request` escalation).

---

## Agent polling protocol

When you (an implementation agent) finish a sub-task and before starting the next:

1. **Read** `agent_states/whispers/<your-agent-id>.md` if it exists. If absent, no whispers — proceed.
2. **Scan from your last cursor** — whispers above your last read are already addressed. Track the last whisper ts in your working memory; never re-process older entries.
3. **Apply severity rules:**
   - `note` — note it; act if you agree with the assessment after reading the body.
   - `strong` — read carefully; default action is to apply the recommendation unless you can justify ignoring it in your final report.
   - `pause` — stop. Write a short status to your spawn output: `paused: waiting on orchestrator (whisper ts: <ts>, detector: <name>)`. Do not start the next sub-task.
4. **Log compliance** — in your final return summary, list the whispers you saw and your response: ignored / followed / paused. Verify reads this to audit whether whispers actually changed behavior.

You do not write to your own whisper file. Only the supervisor writes whispers.

---

## What whispers do NOT do

- They do not block tool calls mid-execution. Polling is voluntary; the cadence is *between* sub-tasks, not inside them.
- They do not replace the orchestrator's escalation ladder. Whispers are agent-directed; the orchestrator's ladder is task-directed.
- They do not carry binding *plan changes*. If the supervisor wants the orchestrator to revise depth or pipeline, it uses an `escalations.jsonl` entry (see `escalations` skill), not a whisper.
- They are not durable across cycles. The whispers/ directory is archived to `cycle_reports/<feature>/supervisor/` at cycle end, then cleared.

## OMP IRC transport (default under omp)

When running under the Oh My Pi (omp) harness, whispers travel over the **irc** tool
instead of the append-only file. irc delivers immediately (no polling), wakes idle
recipients, and persists as `irc:incoming` messages in the recipient's session history.

### Supervisor → implementation agent

Instead of appending to `agent_states/whispers/<agent-id>.md`, the supervisor calls:

```
irc(op: "send", to: "<agent-id>", message: "[<severity>] <detector>: <body>")
```

The severity prefix (`[note]` / `[strong]` / `[pause]`) carries the ladder semantics inline.
The recipient applies the same severity rules as the file path. `pause` is still paired with a
`pause-request` escalation sent to the orchestrator via irc (see `escalations` skill).

### Implementation agent receipt

No polling. irc messages arrive as injected `irc:incoming` turns at the recipient's next step
boundary. The agent reads the message, applies the severity rule, and logs compliance in its
final return summary (same as the file path's step 4).

### Audit trail

File-path whispers archive to `cycle_reports/<feature>/supervisor/whispers/`. Under irc, the
audit trail is each recipient's session JSONL (`history://<agent-id>`). The supervisor should
also echo every whisper it emits to its own return summary so the orchestrator's run report
captures them in one place.

### When to fall back to the file path

The file path is the Claude Code fallback (no irc tool available). Under omp, irc is always
available to subagents (`isIrcEnabled` is true whenever `taskDepth > 0`), so the file path is
only used if irc is explicitly disabled or unavailable.

---

## Supervisor-side format rules

If you are the supervisor:

- One whisper per detector firing — don't batch.
- Body cites a specific event (tool call, file, AC). Vague bodies ("you might be stuck") are worthless.
- For `pause` whispers, you must *also* emit a matching `pause-request` escalation in the same check — they travel as a pair.
- Never write to a whisper file for an agent that hasn't appeared in `events/` yet (the agent doesn't exist, you're hallucinating an ID).
