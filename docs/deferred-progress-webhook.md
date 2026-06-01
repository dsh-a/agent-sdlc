# Deferred — Progress Webhook (synthesis §5.8.6)

**Status:** Deferred (2026-05-31) · **Priority:** P3 · **Source:** culture-improvements honorable mention

A small, optional outbound-notification feature. Captured here so it can be picked up turnkey; not built in the current round.

## What it is

The pipeline POSTs a one-line message to a Discord or Slack incoming webhook at a few key cycle moments, so a user does not have to babysit a running cycle.

Events to emit on:

| Event | Trigger | Example message |
|---|---|---|
| `phase_complete` | a pipeline phase finishes | `[cycle: workout-templates] Phase 3 complete — 4 tasks merged` |
| `agent_question` | a gate or escalation needs user input (cycle is **waiting**) | `[cycle: workout-templates] Waiting on Gate 2 approval` |
| `cycle_error` | stall / watchdog / unrecoverable failure | `[cycle: workout-templates] ERROR — agent test-3.0 stalled` |

The high-value event is `agent_question`: today, if a cycle pauses at a gate while the user is away, they have no signal until they look. This closes that loop.

## Why it's cheap

The `monitor` agent already holds live cycle state (phase, active agents, gate status), so it is the natural emitter. No new agent — the work is a config field plus a thin "fire on these events" step in `monitor`.

## Design sketch

1. **Config** — add to `.claude/config.md` (new optional section, disabled when empty):

   | Field | Value | Notes |
   |---|---|---|
   | `webhook_url` | _(empty)_ | Discord/Slack incoming webhook URL. Empty = disabled. |
   | `webhook_kind` | `discord` \| `slack` | Selects payload shape. |
   | `webhook_events` | `agent_question` (default) | Comma list; opt into `phase_complete` / `cycle_error`. |

   Treat `webhook_url` as a secret — it should live in `settings.local.json` or an env var, **not** be committed. Note this in the config section.

2. **Emitter** — `monitor` (already long-lived for the cycle) sends the POST when it processes a matching state transition. Fire-and-forget: a webhook failure must **never** block, retry-loop, or fail the cycle. Wrap in a timeout; swallow errors.

3. **Payload** — minimal, platform-specific:
   - Discord: `{ "content": "<message>" }`
   - Slack: `{ "text": "<message>" }`

## Open decisions (resolve at pickup)

- **Discord vs Slack vs both.** Supporting both via `webhook_kind` is ~3 extra lines; recommend doing both.
- **Default-on events.** Recommend `agent_question` only by default (highest signal, lowest noise); `phase_complete` and `cycle_error` opt-in.
- **Dashboard link.** Whether to append a link (e.g. to the cycle state file or vault report) — defer unless asked.

## Acceptance criteria

- With `webhook_url` empty, behavior is unchanged (no network calls).
- With it set, an `agent_question` transition produces exactly one POST with the correct platform payload.
- A webhook timeout or non-2xx response is logged and ignored — the cycle proceeds normally.
- The URL is never written to a committed artifact.

## Notes

- Ephemeral *alerting*, distinct from the durable docs-vault artifacts (§5.8 / Docs Vault). No overlap in storage.
- Pairs with the supervisor escalation channel (§5.5) — an escalation is a natural `agent_question` source once that path is wired.
