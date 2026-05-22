# Culture → agent-sdlc: Potential Improvements

Comparison notes from reviewing [agentculture/culture](https://github.com/agentculture/culture) — a persistent-daemon IRC workspace framework — against this repo's phased subagent pipeline. Culture's model (long-lived daemons + workspace presence) is fundamentally different from ours (orchestrator + ephemeral worktreed subagents + gates), so most of it doesn't map. The items below are the patterns that *do*.

---

## Worth borrowing

### 1. In-flight supervision for Phase 3

Implementation agents (`ui-story`, `test`, `scaffold`) currently run inside isolated worktrees and we only see results at wrap-up. Culture's biggest design idea is the cheap sidecar supervisor watching every 5 turns for **SPIRALING / DRIFT / STALLING / SHALLOW**.

Culture's 20-turn × Sonnet-medium cadence is too heavy for us, but a **Haiku-level "review last K tool calls"** check between sub-tasks (or every N tool calls) would catch the failure mode where an agent rewrites the same broken widget six times.

Use Culture's **escalation ladder verbatim**:

1. First detection → whisper (correction note)
2. Issue persists → stronger whisper
3. Still persists → pause agent + alert user

`.claude/skills/cycle/SKILL.md` is where this would slot.

**If we only do one item from this document, it should be this one.** It's the single thing Culture gets dramatically right that our pipeline currently has no analog for.

### 2. Whisper / out-of-band correction channel

Culture queues corrections and piggybacks them on the agent's next tool-call stderr — the agent gets the note without a fresh prompt, mid-turn.

We currently have **no mid-flight correction mechanism**; the only intervention is the user at gate 1C / 2B. Even a primitive version — the `monitor` agent writes to `agent_states/whispers/<agent>.md` and implementation agents are instructed to check between sub-tasks — would let the supervisor (or the user) nudge a worktreed agent without restarting it.

### 3. Explicit context-management at phase boundaries

Culture exposes `compact_context` / `clear_context` as **tools the agent calls itself**.

Our orchestrator runs across long phases with growing context. Have `/cycle` invoke `/compact` deterministically at the **Phase 2 → 3** and **Phase 3 → 4** transitions, where the prior phase's working notes stop being load-bearing. Documented, predictable, and stops the orchestrator from re-reading PRD scaffolding for the 40th time.

### 4. Formal agent I/O contracts

Culture's `agent-harness-spec.md` defines a small structured interface every backend must satisfy:
`start` / `stop` / `send_prompt` / `is_running` / `session_id` + `on_message` / `on_exit` callbacks.

Our agents are markdown prompts where the contract is implicit prose. Add frontmatter like:

```yaml
requires: prd-*.md
produces: tasks-prd-*.md
artifact_dir: agent_tasks/
```

to each `.claude/agents/*.md`. Then the orchestrator can **validate handoffs** (file actually exists, expected schema present) instead of trusting prose. Makes pipeline composition and `/self-improve` analyzable.

---

## Worth ignoring

### IRC / channels / presence / federation

Our model is one human, one conversation, ephemeral subagents. The whole workspace abstraction would be enormous overhead for zero benefit.

### Long-lived daemons / session resume

Claude Code's subagent model doesn't support this, and our worktree-parallelism would have to be sacrificed for it. Not a good trade.

### The full 20×5 supervisor cadence

Too heavy. Our phases are turn-shallow compared to a 24/7 daemon — scale it down to per-task or per-N-tool-calls (see "Worth borrowing #1").

---

## Honorable mentions

Lower leverage but worth keeping on the list.

### Circuit breaker

"3 failures in 5 min → stop & alert." Formalize what's probably already implicit in Phase 3 retry logic. Culture uses this both for agent process crashes and for repeated supervisor escalations.

### Tag-based dispatch

Our `.claude/agents/scaffold/*` subtypes (`syncable-entity`, `view-model-view`, `command`, `facade`, …) are already a taxonomy. Let task files declare:

```yaml
scaffold_kind: syncable-entity
```

and dispatch directly, instead of letting the orchestrator infer from prose. Culture does the analogous thing with agent `tags` for self-organizing rooms.

### Progress webhook

Phase 3 is the longest autonomous stretch. A one-line Discord/Slack poke on `phase_complete` / `agent_question` / `cycle_error` is cheap, and `monitor` already has the state to emit it. Culture's webhook event set (`agent_question`, `agent_spiraling`, `agent_timeout`, `agent_error`, `agent_complete`) is a good starting taxonomy.
