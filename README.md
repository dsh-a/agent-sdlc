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
| `create-prd`, `generate-tasks`, `pre-digest`, `scaffold`, `ui-story`, `coding`, `test`, `test-preflight` | 1–3 | PRD, tasks, implementation |
| `verify`, `review` | 4A | AC audit + code review |
| `monitor`, `supervisor` | — | Cycle state persistence + Phase-3 observation |
| `adversarial-tester` | opt-in | Second-pass test hardening |
| `plan-reviewer` | — | Audits a design plan against the source and a real deployment |
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

### 1. Link into your project

```bash
cd /path/to/your-project
bash ~/dev/agent-sdlc/deploy.sh link .
bash ~/dev/agent-sdlc/deploy.sh gitignore --apply .
bash ~/dev/agent-sdlc/deploy.sh grants             # paste into .claude/settings.json
```

Symlinks, not copies: one checkout, every project current. `deploy.sh check .` verifies a
deployment and reports what is missing.

The links hold absolute paths, so they are per machine. Don't commit them — that is what the
`gitignore` block is for.

### 2. Pick your OpenRouter models

Copy `.omp/models.yml.sample` → `~/.omp/agent/models.yml` and uncomment **one model per tier**,
then set `OPENROUTER_API_KEY` in your env or `<repo>/.env`.

| Tier | omp role | Used by |
|---|---|---|
| opus | `slow` | orchestrator (`/cycle`), verify, review |
| sonnet | `default` / `task` | implementation agents |
| haiku | `smol` | monitor, preflight, supervisor |

The tier ids live in `.omp/agent-config.md` § Model Versions — one place, not copied here.
Uncomment the matching `equivalence.overrides` lines so each model coalesces to its tier id.

Simpler, and what `.omp/models.yml.sample` now recommends: name the provider id directly in
`modelRoles` and skip the tier-label indirection.

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
| `agent_tasks/prds/` (PRDs) | vault, or committed with no vault configured |
| `agent_tasks/tasks-*.md` (task files) | **never committed** |
| `documentation/` (FEATURES, CHANGELOG, DESIGN, …) | committed |
| Stories, bugs, roadmap | **not files** — GitHub Issues + Projects board |
| `agent_states/` (cycle state, telemetry) | **never committed** |
| `cycle_reports/`, `agent_tasks/reports/` | vault or local (see config § Docs Vault) |

Gitignore protection is automatic — on every `/cycle` the orchestrator ensures a managed block
keeps runtime artifacts out of git.

### Trackers live in GitHub

Stories, bugs, the roadmap and the feature backlog are GitHub primitives, not files —
issues by label, hierarchy by sub-issue, ordering by issue dependency, status by board field.
Artifacts of that kind carry the **`remote`** class in `.omp/agent-config.md` § Artifact Paths
and are reached with live `gh` calls; nothing is mirrored locally, and a failed `gh` call is a
stop-and-report rather than a write-a-file fallback.

Point `tracker_repo` at your repo and the board path at your project number. The full
operating contract — including why duplicated facts were removed — is
[`contracts/github-trackers.md`](https://github.com/dsh-a/engineering-meta/blob/main/contracts/github-trackers.md) in **engineering-meta**.

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

Both event hooks resolve their target checkout through `agent_states/.fanout-clone` before falling
back to the git common dir, so a parallel-run clone keeps its own telemetry instead of appending
into the repo it is a linked worktree of. Read a cycle's events back with
`.claude/skills/cycle/aggregate-telemetry.py` rather than opening `agent_states/events/`.

### Configuration lookups

`.omp/agent-config.md` is 360 lines of tables, and an agent that needs one cell from it
currently reads a span. Measured in v0 run 2: ~4,600 tokens, four re-reads after the first came
back truncated, and eleven paragraphs of reasoning about how to resolve a spawn's model.

`.claude/skills/cycle/config-get.py` answers the question instead:

```sh
config-get.py base_branch                       # develop
config-get.py model verify                      # resolved through the Active preset column
config-get.py --keys vault_root app_slug        # several at once; --format env|json
```

Exit 0 found, 1 not found (`--default` supplies one), 2 **ambiguous**, 3 config unreadable.
Ambiguity is an error rather than a guess: `verify` is a row in three different sections, and
silently picking one is how a caller ends up configured by the wrong table.

### Suite results

A test suite's output is the largest single thing an agent reads and the least of it it needs.
Measured in v0 run 2: a scoped `flutter test … | tail -5` put **22,819 characters** into the
orchestrator's context — the harness captures the command's full output whatever the pipe does
with it — and it happened twice, to learn that 81 tests passed.

`.claude/skills/cycle/suite-result.py` runs the suite with its output going to a file and
returns one line: `SUITE <name> PASS tests=3891 failed=0 elapsed=110s log=<path>`, plus failing
test names when red. `run <name> -- <cmd>` runs it; `check <name>` reads a run started by
`run-suite.sh`; `parse <log>` reads any captured output. Exit 0/2/3/4 — passed, failed, still
running, **finished but unparseable**, which is deliberately not conflated with either verdict.

Reporter patterns are stack-specific and live in the pack
(`.claude/packs/<pack>/suite-patterns.md`), so the script itself knows nothing about Dart
or .NET. A project whose reporter nothing matches gets `UNPARSED`, never a guess.

### Test references

`test-preflight` Step 2 greps the test tree for every public symbol the implementer touched and
clusters the hits by test file and test name. All three of those are mechanical; only the verdict
in Step 3 is judgement. Measured in v0 run 2: **6,525 tokens in a single tool call** for the grep
alone, with the clustering then re-derived by reading those lines.

`.claude/skills/cycle/symbol-refs.py` returns the cluster instead:

```sh
symbol-refs.py FooRepository insert find     # scoped to the config's Test path glob
```

```
SYMBOL-REFS hits=9 files=2 symbols=2/3 rows=4 names=resolved glob=test/** pack=flutter
unreferenced: FooViewModel

| Test file | Test name | Symbol | Lines |
|---|---|---|---|
| test/foo/foo_repository_test.dart | FooRepository > inserts row | insert | 13 |
```

Those are Step 4's columns minus `Verdict` and `Reason` — the two the agent is actually for.
Exit 0 hits, **1 no hits** (the greenfield short-circuit `skip_preflight_if_no_existing_tests`
already describes, now branchable on an exit code), 2 bad usage.

Two refusals carry the weight. A symbol with no hits is **named** in `unreferenced:` rather than
dropped, because "nothing references this" and "the grep never ran for it" are indistinguishable
from an absence. And a name is resolved or refused, never composed: a hit inside a test reports
the test, a hit in a `setUp` reports the group alone, and a hit in neither reports `—` with
`names=partial` in the header. An invented test name is a row the test agent will try to find and
cannot.

Test-declaration patterns are stack-specific and live in the pack
(`.claude/packs/<pack>/test-ref-patterns.md`), same table shape and same editing rules as
`suite-patterns.md`.

### One cycle per session

Invoking `/cycle` twice in one session leaves **two copies of the cycle skill
resident**. Measured over 53 orchestrator sessions: all 79 skill injections are
triggered by an explicit `/cycle`, and in 26 of 26 double-invocation sessions
the prompt grows by more than a skill's worth across the second — neither copy
is dropped.

`SKILL.md` is 116,484 characters, which is **43,598 tokens** (2.67 chars/token
by regression over those 26 jumps, not a chars/4 estimate).

| | one `/cycle` | two `/cycle` |
|---|---:|---:|
| Median peak | **235,217** | 278,415 |
| p90 peak | 332,731 | **375,233** |
| Over a 262,144 window | **8/27** | **17/26** |

So the p90 that defines the local-serving gap belongs entirely to the
two-invocation group, and one cycle per session is worth −42,502 tokens on it
for no code change. `/clear` between cycles, or use a new terminal.

Details and the queries behind it:
[`docs/internal/cycle-skill-decomposition-plan.md`](docs/internal/cycle-skill-decomposition-plan.md) § A.

### Known pitfalls

`known-pitfalls.md` is the project's record of bugs that already cost a cycle, and two callers
consume it identically: the orchestrator at Phase 3.3 and `generate-tasks` at Step 5b both read the
whole file and match every entry's `Globs:` line against a task's Relevant Files. Measured in v0
run 2: **5,179 tokens in a single tool call**, and that cost grows with the project's accumulated
bug history rather than with the task.

`.claude/skills/cycle/pitfalls.py` does the matching and returns the block:

```sh
pitfalls.py lib/data/foo_repository.dart      # or --files-from -
```

Output is the `## Known pitfalls for files you'll touch` section § 5.8.3 specifies, `hard` preface
included, ready to paste into a spawn prompt. Exit 0 attach it, 1 attach nothing, **3 no pitfalls
file** — optional configuration, deliberately not conflated with "nothing matched".

Two fail-safes, both pointing the same way. A malformed entry — no `Globs:`, no `Body:` — is
**named** under `unparsed:` with its line number rather than skipped, because a pitfall that
silently stopped applying is the exact failure the mechanism exists to prevent. And an unreadable
`Severity:` reads as **hard**, not `warn`: an unnecessary preface costs a sentence, a missing one
costs the bug again.

Globs are translated to regex rather than fnmatched, so `*` and `?` stay inside a path segment and
the file's `**` means something — `fnmatch` lets `*` cross a `/`, which would make `tests/*` match
`tests/a/b/c`.

### Evidence and absence claims

An agent refining eight stories logged roughly **ten instrumentation errors against zero wrong
claims about the codebase**. The reasoning from evidence held; the gathering of evidence did not.
Two near-published false findings into GitHub issues, including a bug report asserting that
"every `session_set` write has been rejected" for want of an INSERT policy — concluded from
reading **1 of 26** migration files.

Four of those failure classes are one bug four times, and all four are about the shell rather
than the search:

```sh
grep -rn "epic:" . --include=*.md     # zsh ate the glob; the command never ran, and
                                      # inside an && chain that reads as "no results"
grep -rn "foo" lib | head -20; echo $?   # always 0 — that is head's status
grep -c PATTERN file                     # counts matching LINES, not occurrences
grep -rn X missing/dir                   # exit 2, read as exit 1 "no match"
```

`.claude/skills/evidence/evidence.py` answers the question without a shell in the path — no verb
invokes one, and none invokes grep. Patterns are Python `re`, corpora are resolved with
`pathlib`, so the four classes above are unexpressible rather than discouraged:

```sh
evidence.py absence --pattern 'INSERT POLICY' supabase/migrations
```

```
ABSENCE verdict=present pattern=INSERT POLICY unit=paragraph corpus=26/26 files=26 hits=1 occurrences=2
supabase/migrations/0019_session_set_policies.sql:41
```

Seven verbs: `absence`, `anchor` (print bytes to copy into an edit, uniqueness proved),
`guarded-edit` (all-or-nothing, checks by default), `tables` (a row's cell count against its
header's), `cite` (a quoted phrase against the source it is credited to), `round-trip` (what was
pushed is what the destination returns) and `enumerate` (per-item kept/replaced/added/deleted).

Exit 0 the claim holds, 1 it does not, 2 bad usage, 3 **could not determine**. `1` carries this
repo's "refused or no hits" meaning, not grep's — for `absence` it means *present* — so
`verdict=` on the first line of stdout is the primary channel and the exit code the branchable
secondary. A caller who pipes to `head` still reads the verdict.

Three invariants: **a corpus that did not fully resolve exits 3**, even when the part that did
had no hits, with every unresolved path named; **an empty corpus exits 2**, so "state your
corpus" is enforced by argparse; and **nothing accepts an expected total**, because predicted
item counts were wrong three times while the content was right.

The subagents that actually run greps are often built-in harness agents whose bodies the
framework does not own, so they get rules instead of the script: `evidence` § Method rules for a
search subagent holds one fenced block that `/refine` and `create-prd` paste verbatim into their
spawn prompts.

### Story refinement (`/refine`)

Refinement's unit of work is a **probe over an enumerated artifact**, not a topic to consider.
`.claude/skills/refine/probes.py` enumerates a story body's acceptance criteria, unmeasured
numbers, inherited citations, dependency references, prose deferrals and mechanism claims, then
prints each probe's workload; nine probes return a verdict per artifact, and `coverage` reports
the gaps. Coverage is therefore arithmetic rather than a claim — the previous design asked five
personas to self-report `clean`, which a perspective nobody applied prints identically.

`probes.py` owns the probe table and `framework_checks` asserts the skill's copy matches it, so
the two cannot drift. It also owns the `## Open questions` queue, including epic-wide id
allocation; mutating verbs print the whole modified body for `gh issue edit --body-file -`,
changing exactly one line, so a half-write is unexpressible.

`.claude/skills/refine/story.py` is the `gh` half — `load` (one invocation for the issue, its
labels, its board fields, both dependency directions and a gate verdict), `dor` (the
Definition-of-Ready table as a gate that exits 1 naming what is unmet), `set-depth`, and `split`.
It calls `gh` with list argv and never a shell, and every write is dry until `--apply`.

The one probe that asks *who the story is for* reads a project-supplied customer-profile file
(`customer_profiles_path`, vault-class). When that file is absent the probe reports
**`unavailable`**, never `clean` — `pitfalls.py` ran inert in every cycle for months printing a
number nobody read, and an inert gate reads as a passing one.

### Gate wait (Claude Code)

Time spent waiting on a human is usually the largest non-agent cost in a cycle, and wallclock
alone hides it. `.claude/hooks/gate-log.py` — registered on `Stop` and `UserPromptSubmit` —
records every interval between an assistant turn ending and the next prompt, labelling the ones
that match a known gate (Gate 1, Gate 2, the 4B gate, `pr_body_gate`). Unlabelled intervals are
still recorded, so a classification miss never looks like an absence of waiting.

Read it with `.claude/skills/cycle/gate-report.py` (`--log <path>` for a fan-out run's shared
log, `--all` to include unlabelled turns). Phase 4A pastes the summary into the run report's
**Gate wait** section. A gate raised and not yet answered persists as
`agent_states/gate-open.json`, which is how a parked cycle stays visible. No omp equivalent yet —
`start-parallel-cycles.sh` reports at preflight whether capture is active.

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
Phase 4A  Wrap-up             (final tests, cycle report, verify + review, diff review window)
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
| Empty | Checks for active cycles, or offers open `label:feature` issues |

Resume a paused cycle: `/cycle --exe agent_states/cycle-state-[feature-name].md`.

### Opening a terminal window

`.claude/skills/cycle/open-terminal.sh` runs a command in a new terminal window, and is what
`/cycle --parallel` uses to start each fan-out cycle in its own window.

```bash
bash .claude/skills/cycle/open-terminal.sh --cwd ~/dev/app --title "cycle #419" -- 'claude "/cycle 419"'
bash .claude/skills/cycle/open-terminal.sh --tab --cwd ~/dev/app -- 'claude "/cycle 419"'   # tab, not window
```

`--tab` opens a tab in the current window instead. Supported on Ghostty 1.3+ through its
AppleScript dictionary; everywhere else it falls back to a window rather than failing, since
the caller's command still runs either way. macOS will ask for automation consent the first
time, and every AppleScript call is time-bounded so an unanswered dialog degrades to a window
instead of hanging.

Terminals it opens into: Ghostty, iTerm2, WezTerm, kitty, Terminal.app on macOS; Ghostty, WezTerm,
kitty, gnome-terminal, konsole, alacritty, xterm on Linux (or `$TERMINAL`). It exits 0 when a
window opened and 1 when none could be — in an SSH or CI session, or with no emulator found — and
deliberately does **not** decide what that means. A cycle launcher must treat a missing window as a
failure; something advisory should not.

> It is the surviving half of a lazygit diff-review window that used to open at the end of
> Phase 4A. The window was removed in practice as unused; the detection was worth keeping, and
> `start-parallel-cycles.sh` had already grown a second, worse copy of it.

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
