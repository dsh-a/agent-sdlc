# agent-sdlc — workplace fork (`company-a`)

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
  skills/
    project-conventions/         # ACTIVE conventions — loaded by agents deterministically
    context-sources/             # the MCP/RAG plug-in contract
    cycle/                       # the orchestrator
  packs/
    dotnet/                      # default active pack (placeholders — fill via /setup)
    flutter/                     # worked reference example
  agents/                        # the agent team (stack-neutral)
  .mcp.json.sample               # template for connecting your MCP servers
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
| Skill | `context-sources` | The MCP/RAG plug-in contract |
| Agent | `create-prd`, `generate-tasks`, `scaffold`, `ui-story`, `test`, `test-preflight` | Spawned by `/cycle` during Phases 1–3 |
| Agent | `verify`, `review` | Spawned during Phase 4A — AC audit + code review |
| Agent | `monitor`, `supervisor` | Cycle state persistence + Phase-3 observation |
| Agent | `adversarial-tester` | Opt-in second-pass test hardening |
| Agent | `self-improve` | Applies pipeline improvements |

---

## Quick start

### 1. Copy into your project

```bash
cp -r .claude/ /path/to/your-project/.claude/
```

### 2. Run `/setup`

`/setup` detects your stack (`*.sln`/`*.csproj` → dotnet, `pubspec.yaml` → flutter,
`package.json` → node, …), selects a pack, and generates `.claude/config.md` — Project
Commands, Architecture Review Rules, Active Pack, Context Sources, and model preset. It also
populates the active `project-conventions` skill from the chosen pack.

You can also edit `.claude/config.md` directly — it is the single source of customization.

### 3. Connect your MCPs (optional but recommended)

Copy `.claude/.mcp.json.sample` → `.claude/.mcp.json` and fill in your servers (e.g.
`company-a-docs`). Declare each in `.claude/config.md` § Context Sources with the stages it
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
Phase 3   Implementation      (parallel agents in isolated worktrees)
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

`.claude/config.md` is the primary customization point (run `/setup`, or edit directly).

| What to customize | Where |
|---|---|
| Stack / language | `config.md` → **Active Pack** + the pack under `.claude/packs/` |
| Build/test/lint commands | `config.md` → **Project Commands** |
| Layer boundaries & patterns | `config.md` → **Architecture Review Rules** |
| MCP / RAG plug-ins | `config.md` → **Context Sources** + `.claude/.mcp.json` |
| Model spending | `config.md` → **Model Allocation** preset |
| Auto verify/review | `config.md` → **Optional Agents** |
| Conventions (naming, layers) | `.claude/skills/project-conventions/SKILL.md` (from the pack) |
| Permissions | `.claude/settings.json` |

No agent or skill files need editing for routine customization — they read from `config.md`.
