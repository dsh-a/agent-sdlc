# Agent Pipeline Configuration

This file is the central configuration for the agent-sdlc pipeline. Agents and skills read specific sections at runtime. Edit this file directly to customize behavior — or run `/setup` to generate it interactively.

---

## Active Pack

The language/framework pack this project uses. A pack supplies the conventions, test
patterns, anti-patterns, and code idioms for one stack (`.claude/packs/<pack>/`). This field
is informational + used by `/setup`; the *active* conventions are loaded deterministically
from the `project-conventions` skill (see `.claude/packs/README.md` for the swap procedure).

| Field | Value |
|---|---|
| active_pack | `flutter` |

Available packs: `flutter` (default), `dotnet` (alternate template). Author a new one by
copying `.claude/packs/dotnet/` — see `.claude/packs/README.md`.

---

## Artifact Paths

Every artifact is one of three classes:
- **local** — committed to the application repo; travels with the feature branch.
- **runtime** — never committed; covered by the managed `.gitignore` block (cycle state, telemetry, worktrees).
- **vault** — written to the external docs vault when `vault_root` is set (see **Docs Vault** below); otherwise treated as local.

| Artifact | Path | Class |
|---|---|---|
| PRDs and task files | `agent_tasks/` | local |
| Cycle state | `agent_states/` | runtime |
| Telemetry event logs | `agent_states/events/` | runtime |
| Phase-3 worktrees | `.claude/worktrees/` | runtime |
| Cycle reports | `cycle_reports/` | vault |
| Run + verify + review reports | `agent_tasks/reports/` | vault |
| Documentation | `documentation/` | local |
| Feature ideas | `documentation/FEATURES.md` | local |
| Roadmap | `documentation/ROADMAP.md` | local |
| Changelog | `documentation/CHANGELOG.md` | local |

---

## Docs Vault (external artifact store)

When `vault_root` is set, the orchestrator redirects **vault**-class artifacts out of the application repo into a shared, git-backed Obsidian vault. This keeps retrospective process artifacts (cycle reports, run/verify/review reports) out of the product's git history while making them browsable and analyzable across every application that shares the vault. Leave `vault_root` empty to keep these artifacts local (committed to the app repo) — the framework is fully backward-compatible.

| Field | Value | Description |
|---|---|---|
| vault_root |  | Absolute path to the vault root. Empty = disabled. Example: `/Users/you/Documents/ocelot` |
| app_slug |  | Per-application subdirectory inside the vault. Empty = derived from the repo directory name. |

**Resolution.** With `vault_root` set, the orchestrator ensures these symlinks exist at startup (creating the vault targets if missing, migrating any pre-existing local reports into them first) so every relative artifact path resolves into the vault with no per-reference changes:

| Repo path (becomes a symlink) | → Vault target |
|---|---|
| `cycle_reports` | `{vault_root}/cycle_reports/{app_slug}/` |
| `agent_tasks/reports` | `{vault_root}/reports/{app_slug}/` |

The symlinks are added to the managed `.gitignore` block (no trailing slash — git treats a symlink as a file), so the application repo never commits vault artifacts. The vault is versioned by its own git remote (e.g. `ocelot-docs`), independent of any application repo.

---

## Model Allocation

Active preset: **personal**

| Agent | personal | team | enterprise |
|---|---|---|---|
| create-prd | sonnet | sonnet | opus |
| generate-tasks | sonnet | sonnet | opus |
| scaffold | sonnet | sonnet | sonnet |
| ui-story | sonnet | sonnet | sonnet |
| coding | sonnet | sonnet | sonnet |
| test | sonnet | sonnet | sonnet |
| verify | sonnet | sonnet | opus |
| review | sonnet | sonnet | opus |
| adversarial-tester | haiku | haiku | sonnet |
| self-improve | sonnet | sonnet | opus |
| monitor | haiku | haiku | haiku |
| pre-digest | haiku | haiku | haiku |
| salvage | haiku | haiku | haiku |
| test-preflight | haiku | haiku | haiku |
| supervisor | haiku | haiku | haiku |
| orchestrator (/cycle) | opus | opus | opus |

To override a single agent regardless of preset, change the value in that agent's row under the active preset column. The cycle orchestrator reads this table for all agent spawns — implementation agents at Phase 3.3, pre-digest and monitor at Phase 3 start.

### Model Versions

Maps abstract model labels to specific model IDs. When the orchestrator spawns an agent with a label from the allocation table, it uses the version specified here.

| Label | Model ID |
|---|---|
| opus | claude-opus-4-6 |
| sonnet | claude-sonnet-4-5 |
| haiku | claude-haiku-4-5 |

---

## Effort Allocation

| Agent | Effort |
|---|---|
| create-prd | high |
| generate-tasks | high |
| scaffold | medium |
| ui-story | high |
| coding | high |
| test | high |
| verify | max |
| review | max |
| adversarial-tester | high |
| self-improve | high |
| monitor | low |
| test-preflight | low |
| supervisor | low |

---

## Optional Agents

Agents spawned during Phase 4A. Set to `skip` to disable.

| Agent | Status |
|---|---|
| verify | enabled |
| review | enabled |
| supervisor | enabled |

---

## Hygiene flags (§5.8)

Long-tail policy knobs. All default to conservative behavior.

### Analyzer baseline (5.8.1)

| Flag | Default | Behavior |
|---|---|---|
| `analyzer_baseline` | `soft_warn` | `off` — no baseline tracking. `soft_warn` — record analyzer warnings at Phase 3 start; Phase 4A surfaces any new warnings introduced during the cycle but does not block. `hard_fail_if_exceeded` — same recording, but new warnings flip review verdict to REQUEST CHANGES. |

Baseline is recorded into `cycle_reports/<feature>/analyzer-baseline.txt` at Phase 3 start by capturing the **Analyze / lint** command (§ Project Commands) output. Phase 4A re-runs and diffs.

### Compact at phase boundaries (5.8.2)

| Flag | Default | Behavior |
|---|---|---|
| `auto_compact_at_boundaries` | `off` | When `on`, the orchestrator invokes `/compact` at Phase 2→3 and Phase 3→4A transitions to reclaim context. Off by default because compaction can cost orchestrator decision-continuity; enable once your cycles have telemetry showing the trade-off is favorable. |

### Known-pitfalls loop (5.8.3)

| Flag | Default | Behavior |
|---|---|---|
| `known_pitfalls_path` | `documentation/known-pitfalls.md` | Path to the project's known-pitfalls file. If the file exists, the orchestrator pre-attaches matching entries to implementation-agent prompts (matched by file globs). Set to empty string to disable. |

See cycle SKILL § Known pitfalls for the file format.

### Bug-triage (5.8.4)

| Flag | Default | Behavior |
|---|---|---|
| `aggregate_bugs_into` | `documentation/bugs.md` | Path the `self-improve` agent appends new "Bugs discovered" entries to (dedup by title hash). Set to empty string to disable. |

---

## Per-phase skip flags (5.6.2)

Conservative defaults. Flags act as **additional** skip conditions on top of the active `--mode`. Set a flag to `0` or `false` to disable that specific skip.

| Flag | Default | Skips |
|---|---|---|
| `skip_predigest_if_files_lt` | 2 | Pre-digest spawn when the parent task's "Relevant Files" count is below this. (Codifies existing inline rule — small tasks don't need digestion.) |
| `skip_preflight_if_no_existing_tests` | true | `test-preflight` spawn when grep of the **Test path glob** (§ Project Commands) for the touched symbols returns no hits. (Codifies the greenfield short-circuit from 5.4.3.) |
| `skip_review_if_files_lt` | 0 | Review spawn when changed files below this threshold. `0` = always run review. |
| `skip_supervisor_if_total_subtasks_lt` | 3 | Supervisor spawn for the cycle when the task list is small enough that observation overhead exceeds value. |

After ≥ 20 cycles of telemetry, `self-improve` proposes new values based on observed correlations between skipping and downstream rework.

---

## Supervisor Thresholds

Item 5.5.4 placeholders. **All values are best guesses — `self-improve` tunes from real cycle telemetry once enough cycles have run.** Edit here to override.

| Key | Default | Meaning |
|---|---|---|
| `cadence_n` | 5 | Run a supervisor check after every N tool calls per agent |
| `window_k` | 20 | Read the last K events of an agent on each check |
| `stall_seconds` | 300 | An agent with no events for ≥ this duration triggers `stall` |
| `spiral_edits` | 3 | Same file edited this many times without an intervening Read → `spiral` |
| `spiral_errors` | 3 | This many consecutive `exit:error` events → `spiral` |

### Detector states

| Detector | Default | Notes |
|---|---|---|
| `spiral` | enabled | Repeat-edit / repeat-error pattern detection |
| `drift` | enabled | File touches outside the agent's parent-task scope |
| `stall` | enabled | Idle agent above the stall threshold |
| `shallow` | enabled | Edit/Write before any Read of that file |
| `contradiction` | enabled | Cycle-state RESCUE contradiction-loop newer than last check |

Set a detector to `disabled` to silence it without removing the supervisor entirely.

When enabled, these agents run autonomously during Phase 4A and their reports are included in the cycle report. When set to `skip`, the cycle recommends running them manually in separate conversations.

---

## Project Commands

Agents run these commands to test, lint, and generate code. Update to match your project's toolchain. Defaults below target the active pack (`flutter`).

| Purpose | Command |
|---|---|
| Run all tests | `flutter test` |
| Run specific test file | `flutter test <path>` |
| Analyze / lint | `flutter analyze` |
| Code generation | `flutter pub run build_runner build --delete-conflicting-outputs` |
| Test path glob | `test/**` |
| Test anti-patterns | `.claude/packs/flutter/test-antipatterns.md` |

- The `Code generation` command is optional — remove it if your project has no code generation step.
- **Test path glob** is the path the silent-skip gate and preflight short-circuit scope to (default `test/**` for Flutter; .NET-style layouts use `tests/**`).
- **Test anti-patterns** points at the regex list the cycle silent-skip gate greps changed test files against. It defaults to the active pack's file; override per-project here.

---

## Architecture Review Rules

These rules are used by the `review` agent (Step 2) and `verify` agent for convention checks. Customize them to match your project's architecture.

### Layer Boundaries

Define your project's architectural layers and import rules. The review agent checks that files in each layer only import from allowed sources.

| Layer | Path pattern | Allowed imports | Forbidden imports |
|---|---|---|---|
| Domain / Core | `lib/domain/` | Pure Dart, other domain modules | Flutter framework, data layer, `package:provider` |
| Data / Infrastructure | `lib/data/` | Domain layer, external packages | UI layer |
| UI / Presentation | `lib/ui/` | Domain layer via intermediaries (ViewModels, facades, use cases) | Direct data-layer imports |

Adapt path patterns to your project structure. (Defaults shown for the `flutter` pack — MVVM over Clean Architecture; the `dotnet` template uses `src/**/Domain|Application|Infrastructure/`.)

### Pattern Compliance

Describe your project's architectural patterns. The review agent checks that changed files follow these patterns.

- **State management / presentation pattern**: MVVM with `ChangeNotifier` + Provider — ViewModels extend `ChangeNotifier`; Views observe via `context.watch`/`context.read`
- **Views** never call repositories, services, or use cases directly — they go through a ViewModel or equivalent intermediary
- **New dependencies** follow the project's DI pattern — Provider / `MultiProvider`, wired in `lib/dependencies/`
- **Interfaces/abstractions** are used at layer boundaries (e.g., `IRepository<T>`, `IService`)

### Convention Checks

| Convention | Rule |
|---|---|
| Class naming | `PascalCase` |
| Method / variable naming | `camelCase` |
| File naming | `snake_case.dart` |
| Private members | Leading underscore (`_field`, `_method`) |
| Line length | 100 characters max |
| Logging | Project `Logger` from package `logging` (never `print` in production code) |
| Error handling | Async functions have proper error handling at system boundaries (Drift / Supabase / network / external services) |
| Comments | `///` for public API documentation; inline comments explain _why_, not _what_ |

---

## Context Sources (MCP / RAG plug-in points)

External knowledge the pipeline consults at specific stages — a documentation MCP, a
codebase-analysis / RAG service, an ADR store, etc. The orchestrator reads this table and,
at each listed stage, queries the enabled sources **once** and injects the result into the
spawned agent's prompt (the same inject-downward mechanism used for known-pitfalls and the
pre-digest). See `.claude/skills/context-sources/SKILL.md` for the full contract and
`docs/CONTEXT-SOURCES.md` for setup. Connect the actual MCP servers in `.claude/.mcp.json`
(template: `.claude/.mcp.json.sample`).

| id | type | tool / skill | consult_at | required | enabled | query_hint |
|---|---|---|---|---|---|---|
| company-a-docs | mcp | `mcp__company-a-docs__search` | prd, tasks, implement, review | optional | `true` | feature name + domain keywords; engineering/product docs for the touched area |
| codebase-rag | mcp | `mcp__codebase-rag__query` | tasks, implement, verify | optional | `false` | relevant file paths + public symbols; similar prior implementations & constraints |

**Columns.**
- **type** — `mcp` (a connected MCP server; the tool may be deferred — the consumer loads it via `ToolSearch` first) or `skill` (a local skill the orchestrator runs).
- **consult_at** — pipeline stages where this source is queried. Vocabulary: `prd`, `tasks`, `predigest`, `implement`, `review`, `verify`. (`predigest` is excluded for cost by default — the pre-digest is a cheap summarizer.)
- **required** — `optional`: unavailability degrades silently with a logged marker. `required`: unavailability surfaces a gate (and in autonomous mode logs `context-source <id>: DEGRADED` and proceeds). **Never mark an unreleased source `required`.**
- **enabled** — `false` rows are skipped cleanly (e.g. `codebase-rag` until it is released and wired).

---

## Cycle Options

| Option | Value | Description |
|---|---|---|
| auto_verify | `true` | Spawn verify agent during Phase 4A |
| auto_review | `true` | Spawn review agent during Phase 4A |
| feature_idea_on_empty | `true` | When /cycle has no args and no active state, offer to pull from FEATURES.md |
| agent_messaging | `false` | Whether the orchestrator delegates state persistence to a background monitor. `false` (default): the orchestrator writes cycle state inline and only spawns the monitor at Finalize. `true`: a background monitor receives state-update verbs via irc (`irc(op: "wait")`) and maintains the state file. Under omp, irc is always available to subagents, so `true` is viable. Leave `false` for the leanest orchestrator context. |


## Branch Configuration

| Field | Value |
|---|---|
| base_branch | main |
| feature_branch_pattern | feature/[short-description] |
| pr_target | main |

Agents and skills read `base_branch` when running git diffs and creating PRs. Update `pr_target` if your team's PR flow targets a different branch than `base_branch`.
