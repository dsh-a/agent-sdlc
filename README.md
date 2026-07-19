# agent-sdlc — workplace fork

A Claude Code agent team for autonomous feature development. Drop these agents and skills
into your project's `.claude/` directory and get a full SDLC pipeline — from feature idea to
tested, reviewed PR — driven by `/cycle`.

This fork is **language-agnostic with explicit plug-in points**:

- The **core** (orchestrator, agents, pipeline) is stack-neutral. Stack-specific rules live
  in a **pack** (`.claude/packs/<lang>/`). The default active pack is **.NET**; **Flutter**
  ships as a worked reference example.
- External knowledge — a documentation MCP (`company-a-docs`), a RAG codebase-analysis
  service (`codebase-rag`), etc. — plugs in at named pipeline stages via the
  **Context Sources** registry. No code changes to add one: a config row + a connected MCP.

> **New here? Read [`docs/WORKPLACE-SETUP.md`](docs/WORKPLACE-SETUP.md) first.** It walks an
> engineer from clone → connect MCPs → `/setup` → first `/cycle`.

---

## Detailed documentation (read these)

| Doc | Covers |
|---|---|
| [`docs/WORKPLACE-SETUP.md`](docs/WORKPLACE-SETUP.md) | End-to-end onboarding for a new engineer |
| [`docs/CONTEXT-SOURCES.md`](docs/CONTEXT-SOURCES.md) | Wiring MCP / RAG context sources into the cycle |
| [`.claude/README.md`](.claude/README.md) | The `.claude/` layout and the core-vs-pack model |
| [`.claude/packs/README.md`](.claude/packs/README.md) | Authoring a language pack (+ the Flutter example) |
| [`.claude/skills/README.md`](.claude/skills/README.md) | Skill catalog — core vs pack-provided |
| [`.claude/agents/README.md`](.claude/agents/README.md) | Agent catalog, the Phase-3 spawn model, context injection |

---

## The core-vs-pack model

```
.claude/
  config.md                      # the one file you customize (Active Pack, Project Commands,
                                  #   Architecture Rules, Context Sources, model preset)
  skills/                        # discovered by omp via the `claude` provider (priority 80)
    project-conventions/         # ACTIVE conventions — loaded by agents deterministically
    context-sources/             # the MCP/RAG plug-in contract
    cycle/                       # the orchestrator
  packs/
    dotnet/                      # default active pack (placeholders — fill via /setup)
    flutter/                     # worked reference example
  agents/                        # source-of-truth agent bodies (Claude Code path)
  .mcp.json.sample               # template for connecting your MCP servers
.omp/
  agents/                        # 13 omp-native agent definitions (frontmatter + body)
  config.yml                     # omp harness settings (modelRoles → OpenRouter, approval, task)
  models.yml.sample              # OpenRouter provider config + per-tier model menu
  mcp.json.sample                # Context Sources MCP template (omp format)
  AGENTS.md                      # project context (auto-loaded by omp, native priority 100)
  RULES.md                       # sticky hard rules (always-apply)
  hooks/
    log-event.ts                 # telemetry hook (omp JS hook, replaces log-event.py)
```

Switching stacks = pointing **Active Pack** at a different `packs/<lang>/` and populating the
`project-conventions` skill from it (which `/setup` automates). See
[`.claude/packs/README.md`](.claude/packs/README.md).

---

## What's included

| Type | Name | Purpose |
|---|---|---|
| Skill | `/cycle` | Main orchestrator — runs the full pipeline end-to-end |
| Skill | `/create-prd` | Write a PRD from a feature description |
| Skill | `/generate-tasks` | Decompose a PRD into an implementation task list |
| Skill | `/process-tasks` | Step through a task list manually (one sub-task at a time) |
| Skill | `/ui-story` | Build or modify a UI / presentation-layer component |
| Skill | `/test` | Write rigorous, anti-faking tests |
| Skill | `/verify` | Audit whether tests genuinely satisfy acceptance criteria |
| Skill | `/review` | Independent code review before merging |
| Skill | `/scaffold` | Scaffold new components (entities, services, interfaces, UI) |
| Skill | `/feature-idea` | Capture a feature idea and optionally hand off to `/cycle` |
| Skill | `/refine` | Refine a story toward INVEST / Definition-of-Ready |
| Skill | `/self-improve` | Analyze past cycle runs and tune agent/skill instructions |
| Skill | `/setup` | Interactive configuration wizard (detects stack, picks a pack) |
| Skill | `project-conventions` | The active stack's conventions (loaded by agents) |
| Skill | `minimalism` | The reuse-first / YAGNI ladder (loaded by implementers) |
| Skill | `context-sources` | The MCP/RAG plug-in contract |
| Agent | `create-prd`, `generate-tasks`, `scaffold`, `ui-story`, `coding`, `test`, `test-preflight` | Spawned by `/cycle` during Phases 1–3 |
| Agent | `verify`, `review` | Spawned during Phase 4A — AC audit + code review |
| Agent | `monitor`, `supervisor` | Cycle state persistence + Phase-3 observation |
| Agent | `adversarial-tester` | Opt-in second-pass test hardening |
| Agent | `self-improve` | Applies pipeline improvements |

**omp-native features wired in:** native task isolation (replaces manual worktrees), irc for
whispers + escalations + monitor streaming, batch task spawns with `id`/`role`/`isolated`,
`local://` files for on-demand shared context, native session transcripts for supervisor
observation, `explore` bundled agent for codebase scouting, LSP-first code intelligence,
`ast_grep`/`ast_edit` for structural edits, `todo` for phase tracking, `autolearn` for
cross-cycle learning, `advisor` (opt-in second-model review), `memory.backend: local` for
persistent lessons, `retry.modelFallback` for OpenRouter resilience, `contextPromotion` for
overflow recovery, `compaction.midTurnEnabled` for long Phase-3 runs.

---

## Quick start

### 1. Copy into your project

```bash
cp -r .claude/ /path/to/your-project/.claude/
```

### 2. Run `/setup`

`/setup` detects your stack (`*.sln`/`*.csproj` → dotnet, `pubspec.yaml` → flutter,
`package.json` → node, …), selects a pack, and generates `.omp/agent-config.md` — Project
Commands, Architecture Review Rules, Active Pack, Context Sources, and model preset. It also
populates the active `project-conventions` skill from the chosen pack.

You can also edit `.omp/agent-config.md` directly — it is the single source of customization.

### 3. Connect your MCPs (optional but recommended)

Copy `.claude/.mcp.json.sample` → `.claude/.mcp.json` and fill in your servers (e.g.
`company-a-docs`). Declare each in `.omp/agent-config.md` § Context Sources with the stages it
should be consulted at. See [`docs/CONTEXT-SOURCES.md`](docs/CONTEXT-SOURCES.md). The
`codebase-rag` source ships **disabled** until it is released.

### 4. Review permissions

`.claude/settings.json` pre-allows the Bash patterns agents need (defaults target .NET:
`dotnet test`/`build`/`format`) plus `mcp__<source>__*` for your context sources. Adjust to
your toolchain and security preferences. **You must apply this yourself** — the agent cannot
self-edit its own permission file.

### 5. Enable per-agent telemetry (recommended)

`.claude/settings.json` ships a `hooks` block (`PostToolUse` + `SubagentStop`) that appends
one JSONL line per tool call to `agent_states/events/<agent_id>.jsonl`. The run-report
telemetry, the supervisor, and stall salvage all consume this log. Requires `python3` on PATH.

### Conventions: tracked vs runtime

| Directory | Tracked? |
|---|---|
| `agent_tasks/` (PRDs, task files) | committed |
| `documentation/` (FEATURES, ROADMAP, CHANGELOG, …) | committed |
| `agent_states/` (cycle state, telemetry, worktrees) | **never committed** |
| `cycle_reports/`, `agent_tasks/reports/` | vault or local (see config § Docs Vault) |

Gitignore protection is automatic — on every `/cycle` the orchestrator ensures a managed
block keeps runtime artifacts out of git.


## omp + OpenRouter deployment

This branch (`feature/omp-openrouter`) targets the **Oh My Pi (omp)** harness with models
routed through **OpenRouter**. The `.omp/` directory is the native omp adapter layer; `.claude/`
remains the source of truth for skills, packs, and the agent-readable runtime config.

### 1. Pick your OpenRouter models per tier

Copy `.omp/models.yml.sample` → `~/.omp/agent/models.yml` and uncomment **one model per tier**:

| Tier | omp role | Used by | Canonical id |
|---|---|---|---|
| opus | `slow` | orchestrator (`/cycle`), verify, review | `claude-opus-4-6` |
| sonnet | `default` / `task` | implementation agents | `claude-sonnet-4-5` |
| haiku | `smol` | monitor, preflight, supervisor | `claude-haiku-4-5` |

Uncomment the matching `equivalence.overrides` lines so each OpenRouter model coalesces to its
canonical tier id. Set `OPENROUTER_API_KEY` in your env or `<repo>/.env`.

### 2. Connect MCPs (omp format)

Copy `.omp/mcp.json.sample` → `.omp/mcp.json` and fill in your context-source servers. Declare
each in `.omp/agent-config.md` § Context Sources (the orchestrator reads that table at runtime).

### 3. Telemetry (native transcripts + supplementary hook)

Under omp, the **primary** per-agent telemetry is the native session transcript: each subagent
spawned with `id: "<role>-<task-number>"` gets `<id>.jsonl` (full tool-call history) and
`history://<id>` (concise view). The supervisor reads these directly — no hook required for
per-agent event logging.

`.omp/hooks/log-event.ts` is a **supplementary** JS hook that writes a compatibility event log
to `agent_states/events/<agent_id>.jsonl` (matching the Claude Code schema) and bumps the
cadence counter. It's a fallback for the supervisor's file-path detectors, not the primary
signal. omp auto-discovers hooks under `.omp/hooks/`.

**Agent-id resolution:** the orchestrator passes `id: "<role>-<task-number>"` in every task
spawn. This sets the child session's agentId, irc address, registry key, and artifact filename.
The supervisor reads the native transcript (always correctly keyed by `id`) as the primary
source; the hook's agent-id fallback (`OMP_AGENT_NAME` env → "orchestrator") is non-fatal.

### 4. Run `/cycle`

```bash
omp          # launch from the repo root — omp discovers .omp/ + .claude/
/cycle Add CSV export to the reports page
```

omp discovers agents from `.omp/agents/` (native, priority 100), skills from `.claude/skills/`
(claude provider, priority 80), and loads `.omp/AGENTS.md` + `.omp/RULES.md` as context. The
`modelRoles` in `.omp/config.yml` resolve every spawn through your OpenRouter picks.

### 5. Inter-agent messaging (irc)

Under omp, the supervisor's whispers and escalations travel over the **irc** tool instead of
the file-based polling channels. irc delivers immediately, wakes idle recipients, and persists
as `irc:incoming` messages in each recipient's session — no polling, no cursor tracking.

| Channel | File path (Claude Code) | omp irc path |
|---|---|---|
| Whispers (supervisor → impl agent) | `agent_states/whispers/<id>.md` | `irc(op: "send", to: "<id>", …)` |
| Escalations (supervisor → orchestrator) | `agent_states/escalations.jsonl` | `irc(op: "send", to: "Main", …)` |
| Orchestrator collection | poll at 3 moments + cursor | `irc(op: "inbox")` at the same 3 moments |

The `whispers` and `escalations` skills carry an "OMP IRC transport" section documenting the
protocol; the file-based path remains as the Claude Code fallback. The severity ladder
(`note` → `strong` → `pause`) is unchanged — it moves into the irc message body as a
`[severity]` prefix.

### 6. Native task isolation + batch spawns

Phase-3 implementation agents spawn with `isolated: true` — omp captures a baseline from the
feature-branch HEAD, creates an isolated workspace, runs the agent, commits to a task branch
(`omp/task/<id>`), and cherry-picks into the feature branch. This replaces the manual
`git worktree add` + worktree-startup preamble + manual merge/teardown entirely.

Independent parent tasks spawn as a **batch** — one `task` call with a `tasks[]` array, each
item getting its own `id`, `role`, `assignment`, and `isolated: true`. Shared background (PRD
path, AC, context-source blocks, digest) is written to granular `local://` files once; each
agent's `assignment` references only the files it needs, so the agent reads on demand rather
than having all context injected as input tokens. The session semaphore bounds concurrency.

Pre-digest agents run as parallel background **jobs** (`job poll` to collect), overlapping
digestion across independent tasks while the orchestrator does other work.

---

## The `/cycle` skill

`/cycle` is the main entry point. It orchestrates the full pipeline from feature description
to a ready-to-merge PR.

```
/cycle Add CSV export to the reports page          # dry-run: plans, then asks to confirm
/cycle --exe Add CSV export to the reports page    # execute immediately after planning
```

### Pipeline phases

```
Phase 1A  Create PRD          (create-prd agent, you review + approve)
Phase 1C  Gate 1              ("Proceed to tasks?")
Phase 2   Generate task list  (generate-tasks agent, you review + approve)
Phase 2B  Gate 2              ("Begin implementation?")
Phase 3   Implementation      (parallel isolated agents, omp native isolation + batch spawns)
Phase 4A  Wrap-up             (final tests, cycle report, verify + review)
Phase 4B  Release             (push branch, open PR)
```

You interact at gates (1C and 2B). The rest runs autonomously. Context Sources are consulted
at the `prd`, `tasks`, `implement`, `review`, and `verify` stages.

### Starting from different points

| Input | Starts at |
|---|---|
| Feature description (text) | Phase 1A — creates a new PRD |
| PRD file path | Phase 1B — reviews an existing PRD |
| Task file path | Phase 2 — reviews an existing task list |
| State file path | Resume — picks up a paused cycle |
| Empty | Checks for active cycles, or offers ideas from `FEATURES.md` |

Resume a paused cycle: `/cycle --exe agent_states/cycle-state-[feature-name].md`.

---

## Other skills

- **`/process-tasks <task-file>`** — step through a task list manually, one sub-task at a time.
- **`/feature-idea`** — capture a new feature idea and optionally hand off to `/cycle`.
- **`/refine <story-file>`** — refine a single story toward INVEST / Definition-of-Ready.
- **`/self-improve`** — after a few cycles, analyze patterns and tune agent instructions.

---

## Customizing

`.omp/agent-config.md` is the primary customization point (run `/setup`, or edit directly).

| What to customize | Where |
|---|---|
| Stack / language | `config.md` → **Active Pack** + the pack under `.claude/packs/` |
| Build/test/lint commands | `config.md` → **Project Commands** |
| Layer boundaries & patterns | `config.md` → **Architecture Review Rules** |
| MCP / RAG plug-ins | `config.md` → **Context Sources** + `.omp/mcp.json` |
| Model spending | `config.md` → **Model Allocation** + `.omp/config.yml` → `modelRoles` |
| Auto verify/review | `config.md` → **Optional Agents** |
| Conventions (naming, layers) | `.claude/skills/project-conventions/SKILL.md` (from the pack) |
| Permissions / approval | `.omp/config.yml` → `tools.approval` |
| OpenRouter models | `.omp/models.yml.sample` → `~/.omp/agent/models.yml` |
| Task isolation / concurrency | `.omp/config.yml` → `task.*` |
| Advisor / memory / autolearn | `.omp/config.yml` → `advisor.*`, `memory.*`, `autolearn.*` |

No agent or skill files need editing for routine customization — they read from `config.md`.
