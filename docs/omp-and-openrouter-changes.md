# omp + OpenRouter Changes

Living document of all changes made on the `feature/omp-openrouter` branch to optimize the agent-sdlc framework for the Oh My Pi (omp) harness with OpenRouter as the model provider.

Branch base: `develop` (`999ce44`). All changes are uncommitted-to-main; the branch is ready for review or merge when Claude Code compat is no longer needed.

---

## Summary

| Metric | Value |
| Commits | 9 |
| Files changed | 42 |
| Lines added | ~2055 |
| Lines removed | ~496 |
| New `.omp/` files | 19 |
| omp-native agents | 13 |
| omp config settings | 25+ |

---

## Commit 1: `3122cd6` — Native .omp adapter layer + OpenRouter + irc messaging

Created the `.omp/` native adapter layer and wired OpenRouter as the model provider.

### New files (`.omp/`)

| File | Purpose |
|---|---|
| `.omp/agents/*.md` (13 files) | omp-native agent definitions with frontmatter: `model` (omp role), `thinkingLevel`, `tools`, `spawns`, `autoloadSkills`. Bodies sourced from `.claude/agents/`. |
| `.omp/config.yml` | omp harness settings: `modelRoles` (default/smol/slow/task → canonical tier ids), `modelProviderOrder: [openrouter, anthropic]`, `task.isolation.mode: none` (later changed to `auto`), `tools.approval`, `compaction`, `lsp`, `skills` |
| `.omp/models.yml.sample` | OpenRouter provider config + per-tier model menu (opus/sonnet/haiku, 3 options each) + `equivalence.overrides` mapping each pick to its canonical tier id |
| `.omp/mcp.json.sample` | Context Sources MCP template in omp format (with `$schema`) |
| `.omp/AGENTS.md` | Native project context (priority 100, shadows `.claude/CLAUDE.md`) |
| `.omp/RULES.md` | Sticky hard rules (always-apply): never commit runtime artifacts, never edit generated files, stack-specific content in packs, pass model IDs not labels |
| `.omp/hooks/log-event.ts` | JS omp hook factory replacing `.claude/hooks/log-event.py`; listens to `tool_result`/`agent_end`, writes the same JSONL schema |

### Cycle orchestrator (`.claude/skills/cycle/SKILL.md`)

- 14 `Agent(subagent_type:…)` spawn blocks → harness-neutral `Spawn the \`X\` agent (model tier: Y)` notation
- `general-purpose` → `task`; `SendMessage` → `irc`; `run_in_background` → async dispatch
- Supervisor escalation polling: omp drains `irc(op: "inbox")` at 3 decision moments; Claude Code polls `escalations.jsonl` with cursor
- Agent-id stamp: notes the id is the irc address under omp

### Config alignment

- `.claude/config.md` Model Versions table: `opus → claude-opus-4-6`, `sonnet → claude-sonnet-4-5`, `haiku → claude-haiku-4-5` (omp canonical ids)

### Docs

- `README.md`: structure diagram shows `.omp/` alongside `.claude/`; new "omp + OpenRouter deployment" section (5 steps)
- `.claude/README.md`: cross-reference to omp layer
- `.gitignore`: `.omp/mcp.json` added (secrets)

---

## Commit 2: `5815a36` — irc-primary refactor of whispers + escalations

Made irc the primary transport for supervisor↔agent and supervisor↔orchestrator messaging. File-based path collapsed to a brief Claude Code fallback.

### Skills rewritten

| Skill | Lines before | Lines after | Net |
|---|---|---|---|
| `whispers/SKILL.md` | 113 | 70 | −43 |
| `escalations/SKILL.md` | 149 | 43 | −106 |

**whispers**: irc `send` format `[<severity>] <detector>: <body>`; no polling (irc delivers at next step boundary); severity ladder + compliance rules preserved; file-path YAML format collapsed to one-paragraph fallback.

**escalations**: irc `send` format `<type> | agent: <id> | detector: <name> | <fields>`; orchestrator drains `irc(op: "inbox")` at 3 moments (no cursor); three types preserved with pipe-delimited bodies; JSONL schema + cursor collapsed to one-paragraph fallback.

### Agent updates

- `autonomous-agent` preamble: "Whisper polling" → "Whisper handling" (irc inbox drain, not file read)
- omp supervisor body: irc-primary throughout (scope, artifact layout, step 2, "what you send")
- omp agent bodies: `Poll whispers` → `Drain your irc inbox`; `Agent()` → omp-neutral; `general-purpose` kind → `[kind: task]`

---

## Commit 3: `ab1e5fe` — irc wait + agent-id via task `id` + native transcripts

Solved the agent-id problem and the monitor streaming-mode latency problem using omp-native primitives.

### Agent-id via task tool `id` field

The omp task tool's `id` field sets the child session's `agentId`. This single field is now:
- The **irc address** — supervisor sends whispers to `irc(op: "send", to: "test-3.0", …)`
- The **registry key** — `irc(op: "list")` shows it with status
- The **artifact filename** — `test-3.0.jsonl` (full session history), `test-3.0.md` (output)
- The **`history://` reference** — `history://test-3.0` gives a concise transcript

9 spawn blocks in cycle SKILL now include `id:` parameter.

### Supervisor reads native transcripts

The hook-written `agent_states/events/<agent-id>.jsonl` was a Claude Code workaround. omp writes per-agent session transcripts natively (`<id>.jsonl` in the artifacts dir). Supervisor's Step 2 now reads `history://<agent-id>` (concise) or the `<id>.jsonl` artifact (full tool-call detail). All 5 detectors updated to reference "transcript" instead of "events file". The `stall` detector uses `irc(op: "list")` for live agent status.

### Monitor streaming mode uses irc `wait`

Monitor blocks on `irc(op: "wait", from: "Main", timeoutMs: 0)` to receive verbs in real time. Zero latency between orchestrator verb emission and monitor state-file update. `FINALIZE` breaks the loop.

### Hook re-roled as supplementary

`.omp/hooks/log-event.ts`: primary telemetry is now the native transcript. The hook writes a compatibility event log + cadence counter as a fallback. Agent-id resolution via `OMP_AGENT_NAME` env → "orchestrator" fallback is non-fatal since the supervisor reads native transcripts.

### Cadence mechanism

omp path: `irc(op: "list")` for live agents + transcript length for tool-call count approximation. No counter files needed. Claude Code fallback: counter files preserved.

---

## Commit 4: `f891917` — Native isolation + batch spawns + context/role + async pre-digest

Five interconnected omp synergies in one coherent spawn-layer rewrite.

### 1. Native task isolation replaces manual worktrees

`.omp/config.yml`: `task.isolation.mode: auto`, `mergeMode: branch`. Each Phase-3 agent spawns with `isolated: true`; omp captures a baseline from the feature-branch HEAD, creates an isolated workspace, commits to `omp/task/<id>`, and cherry-picks into the feature branch.

**Eliminated:**
- `git worktree add` step
- Worktree-startup preamble (prepended to every spawn prompt)
- `WORKTREE MISMATCH` rescue path
- Manual merge + teardown step
- `.claude/worktrees/` directory and gitignore entry
- Worktree janitor (replaced by task-branch janitor pruning `omp/task/*`)

Implementer + test agent no longer share a worktree. Test agent gets a fresh isolated workspace from the post-merge HEAD — sees committed merged code.

### 2. Shared context via `context` field (later reverted — see Commit 5)

### 3. Agent identity via `role` field

Every spawn includes `role: "<Role> (task <n>)"`. Sets the subagent's system-prompt persona and registry display name, visible in `irc(op: "list")`. Replaces the old `label` frontmatter convention.

### 4. Batch mode for parallel task waves

Independent parent tasks spawn as one `task()` call with a `tasks[]` array. Each item: own `id`, `role`, `assignment`, `isolated: true`. Session semaphore bounds concurrency. Verify + review also batched.

### 5. Job tool for async pre-digest

Pre-digests for independent tasks spawn as parallel background jobs. Orchestrator does other work while digests run. Results collected via `job poll`.

### Other changes

- `config.md`: `agent_messaging` description updated for omp/irc
- `README.md`: section 6 (native isolation + batch spawns)
- Commit protocol simplified (omp already merged)
- Branch strategy updated for native isolation

---

## Commit 5: `55f2578` — local:// files instead of context field (token economy fix)

**Problem:** the `context` field raw-injects all shared background as input tokens into every spawned subagent's system prompt. This broke per-agent context curation and increased token spend on lightweight agents.

**Fix:** switched to `local://` files. Each piece of shared background written once to a granular file. Each agent's `assignment` references only the files it needs. Agent reads on demand via `read` tool.

| File | Contents | Who reads it |
|---|---|---|
| `local://prd.md` | PRD path + feature description | implementer, test, verify, review |
| `local://ac.md` | Pre-extracted AC from PRD | test, verify, implementer |
| `local://ctx-sources.md` | Context-source blocks (stage `implement`) | implementer, test |
| `local://digest-<task>.md` | Pre-digest summary for task N | implementer for task N only |
| `local://commands.md` | Project Commands (test, analyze, codegen) | any agent that runs them |

`context` field now carries only a minimal one-liner. Pre-flight agent's `assignment` has no `local://` references — zero shared context tokens. Test agent references `local://ac.md` + `local://ctx-sources.md` but NOT the digest. Per-agent curation preserved.

All spawn blocks updated: Phase 1A, Phase 2, Phase 3.3 (pre-digest, implement, pre-flight, test), Phase 4A (verify, review), stall salvage.

---

## Commit 6: `9aa063e` — LSP-first + ast tools + explore agent + todo + autolearn

Five omp tool synergies.

### 1. LSP-first code intelligence

`autonomous-agent` preamble (loaded by every agent) now instructs: prefer `lsp` for `definition`/`references`/`rename`/`diagnostics` over `grep`. Catches shadowed names grep misses; safer renames; early diagnostics. `grep` demoted to plain-text lookup only.

### 2. ast_grep + ast_edit for structural code search/rewrite

Added to tools of 7 agents (coding, scaffold, test, ui-story, verify, review, self-improve). Preamble instructs: `ast_grep` for syntactic pattern search, `ast_edit` for structural codemods with capture substitution. Use `grep` only for lexical patterns.

### 3. Bundled explore agent for codebase scouting

Replaced two generic `task` spawns with omp's built-in `explore` agent (read-only, fast, compressed context):
- `create-prd` Step 2: codebase exploration before writing the PRD
- `cycle` SKILL 3.1: setup-scaffold pattern discovery

### 4. Todo tool for orchestrator phase tracking

Cycle SKILL entry point: initialize `todo` with 7 pipeline phases. Mark `in_progress` on entry, `done` on completion. Visible in TUI. On resume, re-initialize and mark completed phases `done`.

### 5. Autolearn for cross-cycle learning

`.omp/config.yml`: `autolearn.enabled: true` (passive). omp nudges agents to capture lessons after stopping. `self-improve` Step 1 now reads `~/.omp/agent/managed-skills/` for autolearn-captured lessons alongside run reports.

### Bonus

- `web_search` added to verify + review (check API docs, best practices, security advisories)
- Stale Phase 3.1 sections cleaned (irc transport, native isolation, transcript refs)

---

## Commit 7: `f225610` — Advisor + memory + retry/fallback + browser/eval + docs sweep

### Config synergies (`.omp/config.yml`, 10 new settings)

| Setting | What it does |
|---|---|
| `advisor` (opt-in) | Second model reviews each orchestrator turn; catches planning mistakes. Uses smol tier (cheap). |
| `memory.backend: local` | Cross-cycle persistent lessons; feeds orchestrator on resume + self-improve. |
| `retry.modelFallback: true` | OpenRouter resilience — falls back to another model when one is unavailable. |
| `contextPromotion: enabled` | Overflow recovery — promotes to larger-context sibling before compaction. |
| `compaction.midTurnEnabled: true` | Checks thresholds between tool-loop requests (long Phase-3 runs). |
| `task.maxConcurrency: 4` | Bounds parallel Phase-3 agents. |
| `task.maxRecursionDepth: 2` | Agent-spawning-agent depth. |
| `task.agentIdleTtlMs: 600000` | 10-min idle TTL for irc follow-ups. |
| `thinkingBudgets` | Per-tier token budgets (low/medium/high/xhigh). |
| `tier.subagent: inherit` | Subagents inherit main agent's service tier. |

### Agent tool additions

- `ui-story` +`browser` (UI visual testing, screenshot verification)
- `test` +`eval` (persistent Python/JS kernel for quick computations)
- `verify` +`eval` (verify test logic, compute coverage metrics)

### Docs sweep (6 files)

| File | What changed |
|---|---|
| `CLAUDE.md` | Rewritten — structure shows `.omp/` + `.claude/`, harness target documented |
| `docs/WORKPLACE-SETUP.md` | Rewritten — 6-step omp + OpenRouter onboarding |
| `.claude/skills/context-sources/SKILL.md` | Rewritten — `local://` files, no `ToolSearch`, omp auto-discovers MCP tools |
| `docs/CONTEXT-SOURCES.md` | Updated — `local://` files, `.omp/mcp.json`, no permission allowlist |
| `.claude/packs/README.md` | Updated — switch steps reference `.omp/agents/` + `.omp/config.yml` |
| `.omp/AGENTS.md` + `README.md` | Config description + "What's included" table updated |

---

## Current agent tool matrix

| Agent | Tools |
|---|---|
| adversarial-tester | read, grep, glob, edit, write, bash |
| coding | read, grep, glob, ast_grep, ast_edit, edit, write, bash, lsp, irc |
| create-prd | read, grep, glob, write, bash |
| generate-tasks | read, grep, glob, write, bash |
| monitor | read, write, glob, bash, irc |
| review | read, grep, glob, ast_grep, ast_edit, write, edit, bash, lsp, web_search |
| scaffold | read, grep, glob, ast_grep, ast_edit, edit, write, bash, lsp, irc |
| self-improve | read, grep, glob, ast_grep, ast_edit, edit, write, lsp |
| supervisor | read, write, glob, grep, bash, irc |
| test-preflight | read, grep, glob |
| test | read, grep, glob, ast_grep, ast_edit, edit, write, bash, lsp, irc, eval, debug |
| ui-story | read, grep, glob, ast_grep, ast_edit, edit, write, bash, lsp, irc, browser |
| verify | read, grep, glob, ast_grep, ast_edit, write, edit, bash, lsp, web_search, eval |

---

## Known limitations

1. **Hook agent-id**: omp doesn't expose the subagent name to hooks via a stable env var. The hook falls back to "orchestrator". Non-fatal because the supervisor reads native transcripts (always correctly keyed by `id`).
2. **`.claude/agents/` stale**: the `.claude/agents/` versions of monitor + supervisor still have file-based references. They're the Claude Code fallback; the `.omp/agents/` versions are omp-primary. Cycle SKILL path refs now point to `.omp/agents/`.
3. **Claude Code compat**: untested and likely broken at the spawn layer. Accepted per the branch's purpose.
4. **`.claude/config.md` path**: stays at `.claude/config.md` (agents read it by file path — works under omp). Renaming to `.omp/` is a follow-up.

---

## Commit 8: `b334dce` — Stale ref cleanup + OpenRouter routing + debug + checkpoint + profiles

### Category A — stale reference cleanup (8 files, refs updated not deleted)

Decision: keep `.claude/agents/` and other Claude Code files in place (omp ignores them for agent discovery). Only update path references that the cycle SKILL or templates read by path.

| File | What changed |
|---|---|
| `.claude/skills/cycle/SKILL.md` | `.claude/agents/monitor.md` → `.omp/agents/monitor.md`; `.claude/agents/self-improve.md` → `.omp/agents/self-improve.md` |
| `.claude/skills/cycle/monitor.md` | `SendMessage` → `irc(op: "wait")`; worktree paths → isolated workspace paths |
| `.claude/skills/cycle/state-template.md` | Worktree path column → task branch; dropped escalation cursor section (irc inbox replaces it) |
| `.claude/skills/cycle/report-template.md` | `PostToolUse` hook refs → omp native transcripts (`<id>.jsonl` + `history://<id>`) |
| `.claude/skills/setup/SKILL.md` | `.claude/.mcp.json` → `.omp/mcp.json`; dropped permission allowlist step; added omp settings confirmation step; updated summary with omp next steps |
| `README.md` customizing table | `.claude/settings.json` → `.omp/config.yml`; added OpenRouter models, task isolation, advisor/memory rows |

### Category B — OpenRouter routing optimizations

**`.omp/models.yml.sample`** — per-model `compat` blocks added:
- `openRouterRouting.only: [anthropic]` on Claude models — pins to Anthropic upstream, prevents quality degradation from fallback providers
- `cacheControlFormat: anthropic` on Claude models — enables prompt caching on OpenRouter's `anthropic/*` models, reduces cost on repeated system prompts (significant for the cycle orchestrator)
- `openRouterRouting.order` on non-Anthropic models — provider preference order

**`.omp/config.yml`** — `providers.openrouterVariant` setting:
- `nitro`: fastest inference (good for haiku tier — latency-sensitive monitor/preflight)
- `floor`: cheapest (cost optimization for lightweight agents)
- `online`: highest availability (avoid rate limits during parallel Phase-3 waves)
- `exacto`: exact model match (no provider fallback — strictest quality)
- `default`: standard routing

### Category C — new omp tool integrations

| Feature | Where | What it does |
|---|---|---|
| `debug` tool | `.omp/agents/test.md` | Step through failing tests with breakpoints, inspect variables, evaluate expressions — instead of reading code and guessing |
| `checkpoint`/`rewind` | `.claude/skills/cycle/SKILL.md` | Orchestrator checkpoints before risky ops (L3 reverts, scope changes, complex merges); rewinds on failure instead of full cycle restart |
| Profiles | `docs/WORKPLACE-SETUP.md` | `omp --profile <name>` for team workflows — isolated MCP + model roles per engineer, shared pipeline config |
| `statusLine` | `.omp/config.yml` | `preset: full` — show model + cwd + git branch in TUI |


---

## Next items to explore

- **omp `plan` mode mapping** — the cycle already has a dry-run (Phases 1–2 + dependency analysis, then present a plan). omp's native plan mode (`--plan` / `plan` agent) is a read-only planning surface that restricts tools to `read`/`search`/`find`/`lsp`/`web_search`. Could map the cycle's dry-run to omp's plan mode so the orchestrator's planning phase is tool-restricted natively, preventing accidental implementation during dry-run.

- **omp `session export/share/fork`** — omp can export, share, fork, and resume sessions. A completed cycle's session could be exported and shared with another engineer for review, or forked to try a different approach without losing the original. The cycle report + run report are file-based artifacts; session export would give a conversational artifact (the full orchestrator transcript) alongside them.

- **omp `marketplace` skills** — omp has a skills marketplace for installable skill packs. The framework's skills (whispers, escalations, autonomous-agent, minimalism, etc.) could be packaged as a marketplace skill pack that other omp users install into their projects, decoupling the framework from the `.claude/skills/` directory.

- **Custom omp extensions (JS/TS hooks beyond logging)** — the current `.omp/hooks/log-event.ts` is a telemetry hook. omp hooks can also block/modify tool calls (`tool_call` event), inject context (`context` event), register slash commands, and register custom message renderers. Potential uses: a hook that auto-approves specific bash patterns based on the active pack (replacing the Claude Code per-pattern allowlist), a hook that injects known-pitfalls matching the current file context, a hook that blocks edits to generated files.

- **`.claude/config.md` → `.omp/agent-config.md` rename** — 42 references across agents, skills, and packs point at `.claude/config.md`. Moving it to `.omp/agent-config.md` would fully purge the `.claude/` path from the omp-first branch. Deferred because it's a large find-replace with no behavioral change; worth doing before merging to `main`.

- **omp `collab` (multi-agent collaboration)** — omp has a collab feature for real-time multi-agent collaboration. The cycle's Phase-3 parallel agents currently run as independent isolated spawns with no shared state. Collab could let parallel agents share a live context (e.g., two implementers working on interdependent tasks see each other's progress in real time via irc broadcast). Needs investigation — may conflict with the isolation model.

- **omp `ttsr` (time-traveling stream rules)** — omp has time-traveling stream rules that re-attach rules near the current turn after context growth. The framework's `RULES.md` is already sticky (always-apply), but `ttsr` could be used to re-inject phase-specific rules (e.g., "you are in Phase 3 — do not edit the PRD") at the right moments without polluting the opening context.

- **OpenRouter `extraBody` for gateway hints** — the `compat.extraBody` field in `models.yml` can send arbitrary top-level fields to OpenRouter (gateway hints, controller selectors). Could be used for team-specific routing preferences (e.g., route to a specific provider pool during business hours, a cheaper pool after hours).

- **omp `learn` / `retain` / `reflect` tools** — omp has memory tools (`learn`, `retain`, `recall`, `reflect`) that work with the memory backend. The `self-improve` agent currently reads run reports + managed-skills. It could also use `recall` to pull cross-cycle patterns from memory and `reflect` to synthesize improvement recommendations from accumulated lessons.