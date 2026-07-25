# agent-sdlc

An agent team that takes a feature from idea to a tested, reviewed PR — autonomously,
driven by a single `/cycle` command. It runs a full SDLC pipeline: PRD → task breakdown →
parallel implementation → test → verify → review → PR.

**Language-agnostic by design.** The core pipeline is stack-neutral; stack-specific rules
live in a swappable **pack** (`.claude/packs/<lang>/`). Flutter ships active by default,
with .NET as an alternate template.

**Pluggable knowledge sources.** Wire in external context — a documentation MCP, a RAG
codebase-analysis service (e.g. `company-a-docs`, `codebase-rag`) — at named pipeline stages
through the **Context Sources** registry. Adding one is a config row plus a connected MCP; no
code changes.

**Runs on Claude Code, Pi, and Oh My Pi (omp), and is OpenRouter ready** — route every
agent through the models you choose.

> **New here?** Start with [`docs/SETUP.md`](docs/SETUP.md) — clone → connect MCPs →
> `/setup` → first `/cycle`.

---

## Documentation

| Path | What it is |
|---|---|
| [`docs/SETUP.md`](docs/SETUP.md) | Onboarding guide — zero to a first `/cycle` run. |
| [`docs/CONTEXT-SOURCES.md`](docs/CONTEXT-SOURCES.md) | Operator's guide to the MCP / RAG context-source registry. |

---

## Layout

```
.claude/                       # the pipeline — copy into a project to install
  skills/                      # /cycle orchestrator, entry-point commands, agent rubrics
    cycle/                     #   the orchestrator
    project-conventions/       #   ACTIVE stack conventions (loaded by agents)
    context-sources/           #   the MCP / RAG plug-in contract
  packs/                       # swappable language packs
    flutter/                   #   default active pack
    dotnet/                    #   alternate template (fill via /setup)
  agents/                      # source-of-truth agent bodies
  .mcp.json.sample             # MCP template (Claude Code path)
.omp/                          # native Oh My Pi adapter layer
  agent-config.md              # ★ the one file you customize (Active Pack, Project Commands,
                               #   Architecture Rules, Context Sources, model preset)
  agents/                      # omp-native agent definitions
  config.yml                   # harness settings (modelRoles → OpenRouter, approval, task)
  models.yml.sample            # OpenRouter provider config + per-tier model menu
  mcp.json.sample              # Context Sources MCP template (omp format)
  AGENTS.md                    # project context (auto-loaded by omp)
  RULES.md                     # sticky hard rules (always-apply)
  hooks/log-event.ts           # supplementary telemetry hook
```

## The core-vs-pack model

The **core** — orchestrator, agents, skills — is stack-neutral. Everything a specific stack
needs lives in a **pack** under `.claude/packs/<lang>/`: conventions, test patterns, idioms.
Switching stacks means pointing **Active Pack** at a different `packs/<lang>/` and populating
the `project-conventions` skill from it — which `/setup` automates. See
[`.claude/packs/README.md`](.claude/packs/README.md).

---

## What's included

**Commands** — slash-invocable skills:

| Command | Purpose |
|---|---|
| `/cycle` | Run the full pipeline end-to-end (the main entry point) |
| `/setup` | Configuration wizard — detects the stack, picks a pack |
| `/create-prd` | Write a PRD from a feature description |
| `/generate-tasks` | Decompose a PRD into an implementation task list |
| `/process-tasks` | Step through a task list manually, one sub-task at a time |
| `/scaffold` | Scaffold new components (entities, services, interfaces, UI) |
| `/ui-story` | Build or modify a UI / presentation-layer component |
| `/test` | Write rigorous, anti-faking tests |
| `/verify` | Audit whether tests genuinely satisfy acceptance criteria |
| `/review` | Independent code review before merging |
| `/feature-idea` | Capture a feature idea, optionally hand off to `/cycle` |
| `/refine` | Refine a story toward INVEST / Definition-of-Ready |
| `/self-improve` | Analyze past cycle runs and tune agent/skill instructions |

Agents also load internal skills that aren't invoked directly — `project-conventions` (active
stack rules), `minimalism` (the reuse-first ladder), `context-sources` (the plug-in contract),
plus the output-format rubrics.

**Agents** — spawned by `/cycle`:

| Agent | Phase | Role |
|---|---|---|
| `create-prd`, `generate-tasks`, `scaffold`, `ui-story`, `coding`, `test`, `test-preflight` | 1–3 | PRD, tasks, implementation |
| `verify`, `review` | 4A | AC audit + code review |
| `monitor`, `supervisor` | — | Cycle state persistence + Phase-3 observation |
| `adversarial-tester` | opt-in | Second-pass test hardening |
| `self-improve` | — | Applies pipeline improvements |

---

## omp-native integration

Run on Oh My Pi, the pipeline uses the harness's native machinery instead of the file-based
Claude Code fallbacks:

| Capability | What it does |
|---|---|
| **Task isolation + batch spawns** | Each Phase-3 agent runs in an isolated workspace (`isolated: true`, no manual worktrees); independent tasks spawn together in one batch, each with its own `id`/`role`. |
| **irc messaging** | The `irc` tool carries supervisor whispers, escalations, and monitor streaming — delivered immediately, no polling. |
| **Shared context** | `local://` files hold on-demand shared context; native session transcripts feed supervisor observation. |
| **Code intelligence** | The `explore` scouting agent, LSP-first navigation, and `ast_grep` / `ast_edit` structural edits. |
| **Cross-cycle learning** | `todo` phase tracking, `autolearn` lessons, `advisor` (opt-in second-model review), and persistent lessons via `memory.backend: local`. |
| **OpenRouter resilience** | `retry.modelFallback` (retry a failed call on another model), `contextPromotion` (context-overflow recovery), and `compaction.midTurnEnabled` (mid-turn compaction for long Phase-3 runs). |

---

## Quick start

### 1. Copy into your project

```bash
cp -r .claude/ /path/to/your-project/.claude/
cp -r .omp/    /path/to/your-project/.omp/
```

### 2. Pick your OpenRouter models

Copy `.omp/models.yml.sample` → `~/.omp/agent/models.yml` and uncomment **one model per tier**,
then set `OPENROUTER_API_KEY` in your env or `<repo>/.env`.

| Tier | omp role | Used by | Canonical id |
|---|---|---|---|
| opus | `slow` | orchestrator (`/cycle`), verify, review | `claude-opus-4-6` |
| sonnet | `default` / `task` | implementation agents | `claude-sonnet-4-5` |
| haiku | `smol` | monitor, preflight, supervisor | `claude-haiku-4-5` |

Uncomment the matching `equivalence.overrides` lines so each model coalesces to its canonical
tier id.

### 3. Run `/setup`

`/setup` detects your stack (`pubspec.yaml` → flutter, `*.sln`/`*.csproj` → dotnet,
`package.json` → node, …), selects a pack, and generates `.omp/agent-config.md` — Project
Commands, Architecture Review Rules, Active Pack, Context Sources, and model preset — then
populates the active `project-conventions` skill from the pack. You can edit
`.omp/agent-config.md` directly at any time; it's the single source of customization.

To wire in knowledge sources, copy `.omp/mcp.json.sample` → `.omp/mcp.json`, fill in your
servers, and declare each in `.omp/agent-config.md` § Context Sources with the stages it should
be consulted at (see [`docs/CONTEXT-SOURCES.md`](docs/CONTEXT-SOURCES.md)). The `codebase-rag`
source ships **disabled** until it is released.

### 4. Run `/cycle`

```bash
omp          # launch from the repo root — omp discovers .omp/ + .claude/
/cycle Add CSV export to the reports page
```

> Full onboarding — prerequisites, permissions, and troubleshooting — lives in
> [`docs/SETUP.md`](docs/SETUP.md).

### Tracked vs runtime files

| Directory | Tracked? |
|---|---|
| `agent_tasks/` (PRDs, task files) | committed |
| `documentation/` (FEATURES, ROADMAP, CHANGELOG, …) | committed |
| `agent_states/` (cycle state, telemetry) | **never committed** |
| `cycle_reports/`, `agent_tasks/reports/` | vault or local (see config § Docs Vault) |

Gitignore protection is automatic — on every `/cycle` the orchestrator ensures a managed block
keeps runtime artifacts out of git.

---

## How it runs on omp

The `.omp/` directory is the native omp adapter layer; `.claude/` remains the source of truth
for skills, packs, and the agent-readable runtime config.

### Harness discovery

omp discovers agents from `.omp/agents/` (native, priority 100) and skills from
`.claude/skills/` (claude provider, priority 80), and loads `.omp/AGENTS.md` + `.omp/RULES.md`
as context. The `modelRoles` in `.omp/config.yml` resolve every spawn through your OpenRouter
picks.

### Telemetry

Per-agent telemetry is the native session transcript: each subagent spawned with
`id: "<role>-<task-number>"` gets a `<id>.jsonl` tool-call history (and a concise
`history://<id>` view) that the supervisor reads directly. `.omp/hooks/log-event.ts` supplements
it with a compatibility event log under `agent_states/events/` — no external hook runtime
required. The file-based `.claude/settings.json` hooks are the Claude Code equivalent.

### Inter-agent messaging (irc)

Supervisor whispers and escalations travel over the `irc` tool — delivered immediately, waking
idle recipients, no polling. The file-based paths are the Claude Code equivalent.

| Channel | omp (irc) | Claude Code (files) |
|---|---|---|
| Whispers (supervisor → impl agent) | `irc(op:"send", to:"<id>", …)` | `agent_states/whispers/<id>.md` |
| Escalations (supervisor → orchestrator) | `irc(op:"send", to:"Main", …)` | `agent_states/escalations.jsonl` |
| Orchestrator collection | `irc(op:"inbox")` | poll at 3 moments + cursor |

The severity ladder (`note` → `strong` → `pause`) rides in the message body as a `[severity]`
prefix.

### Task isolation + batch spawns

Phase-3 implementation agents spawn with `isolated: true`: omp captures a baseline from the
feature-branch HEAD, runs the agent in an isolated workspace, commits to a task branch
(`omp/task/<id>`), and cherry-picks back into the feature branch — no manual worktrees.
Independent tasks spawn as one **batch**, each with its own `id`/`role`; shared background (PRD
path, AC, context-source blocks) is written once to granular `local://` files that each agent
reads on demand rather than receiving as injected tokens. Pre-digest agents run as parallel
background jobs, overlapping digestion across tasks.

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

## Customizing

Run `/setup`, or edit `.omp/agent-config.md` directly:

| What to customize | Where |
|---|---|
| Stack / language | `.omp/agent-config.md` → **Active Pack** + the pack under `.claude/packs/` |
| Build/test/lint commands | `.omp/agent-config.md` → **Project Commands** |
| Layer boundaries & patterns | `.omp/agent-config.md` → **Architecture Review Rules** |
| MCP / RAG plug-ins | `.omp/agent-config.md` → **Context Sources** + `.omp/mcp.json` |
| Model spending | `.omp/agent-config.md` → **Model Allocation** + `.omp/config.yml` → `modelRoles` |
| Auto verify/review | `.omp/agent-config.md` → **Optional Agents** |
| Conventions (naming, layers) | `.claude/skills/project-conventions/SKILL.md` (from the pack) |
| Permissions / approval | `.omp/config.yml` → `tools.approval` |
| OpenRouter models | `.omp/models.yml.sample` → `~/.omp/agent/models.yml` |
| Task isolation / concurrency | `.omp/config.yml` → `task.*` |
| Advisor / memory / autolearn | `.omp/config.yml` → `advisor.*`, `memory.*`, `autolearn.*` |

No agent or skill files need editing for routine customization — they read from `.omp/agent-config.md`.
