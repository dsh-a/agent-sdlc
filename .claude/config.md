# Agent Pipeline Configuration

This file is the central configuration for the agent-sdlc pipeline. Agents and skills read specific sections at runtime. Edit this file directly to customize behavior — or run `/setup` to generate it interactively.

---

## Artifact Paths

| Artifact | Path |
|---|---|
| PRDs and task files | `agent_tasks/` |
| Cycle state (ephemeral) | `agent_states/` |
| Cycle reports | `cycle_reports/` |
| Run reports | `agent_tasks/reports/` |
| Documentation | `documentation/` |
| Feature ideas | `documentation/FEATURES.md` |
| Roadmap | `documentation/ROADMAP.md` |
| Changelog | `documentation/CHANGELOG.md` |

---

## Model Allocation

Active preset: **personal**

| Agent | personal | team | enterprise |
|---|---|---|---|
| create-prd | sonnet | sonnet | opus |
| generate-tasks | sonnet | sonnet | opus |
| scaffold | sonnet | sonnet | sonnet |
| ui-story | sonnet | sonnet | sonnet |
| test | sonnet | sonnet | sonnet |
| verify | sonnet | sonnet | opus |
| review | sonnet | sonnet | opus |
| adversarial-tester | haiku | haiku | sonnet |
| self-improve | sonnet | sonnet | opus |
| monitor | haiku | haiku | haiku |
| pre-digest | haiku | haiku | haiku |
| orchestrator (/cycle) | opus | opus | opus |

To override a single agent regardless of preset, change the value in that agent's row under the active preset column. The cycle orchestrator reads this table for all agent spawns — implementation agents at Phase 3.3, pre-digest and monitor at Phase 3 start.

---

## Effort Allocation

| Agent | Effort |
|---|---|
| create-prd | high |
| generate-tasks | high |
| scaffold | medium |
| ui-story | high |
| test | high |
| verify | max |
| review | max |
| adversarial-tester | high |
| self-improve | high |
| monitor | low |

---

## Optional Agents

Agents spawned during Phase 4A. Set to `skip` to disable.

| Agent | Status |
|---|---|
| verify | enabled |
| review | enabled |

When enabled, these agents run autonomously during Phase 4A and their reports are included in the cycle report. When set to `skip`, the cycle recommends running them manually in separate conversations.

---

## Project Commands

Agents run these commands to test, lint, and generate code. Update to match your project's toolchain.

| Purpose | Command |
|---|---|
| Run all tests | `flutter test` |
| Run specific test file | `flutter test <path>` |
| Analyze / lint | `flutter analyze` |
| Code generation | `flutter pub run build_runner build --delete-conflicting-outputs` |

The `Code generation` command is optional — remove it if your project has no code generation step.

---

## Architecture Review Rules

These rules are used by the `review` agent (Step 2) and `verify` agent for convention checks. Customize them to match your project's architecture.

### Layer Boundaries

Define your project's architectural layers and import rules. The review agent checks that files in each layer only import from allowed sources.

| Layer | Path pattern | Allowed imports | Forbidden imports |
|---|---|---|---|
| Domain / Core | `lib/domain/` | Pure Dart, other domain modules | Flutter framework, data layer, `package:provider` |
| Data / Infrastructure | `lib/data/` | Domain layer, external packages | UI layer |
| UI / Presentation | `lib/ui/` | Domain layer via intermediaries (ViewModels, facades, use cases) | Direct data layer imports |

Adapt path patterns to your project structure.

### Pattern Compliance

Describe your project's architectural patterns. The review agent checks that changed files follow these patterns.

- **State management**: _[describe your pattern — e.g., MVVM with ChangeNotifier + Provider, Riverpod, BLoC, GetX]_
- **Views** never call repositories, services, or use cases directly — they go through a ViewModel or equivalent intermediary
- **New dependencies** follow the project's DI pattern — _[describe your DI approach, e.g., Provider/MultiProvider, get_it, manual factory]_
- **Interfaces/abstractions** are used at layer boundaries (e.g., `IRepository`, `IService`)

### Convention Checks

| Convention | Rule |
|---|---|
| Class naming | `PascalCase` |
| Method/variable naming | `camelCase` |
| File naming | `snake_case` |
| Private members | Leading underscore (`_field`, `_method`) |
| Line length | 100 characters max |
| Logging | Project logger (never `print` in production code) |
| Error handling | Async functions have proper error handling at system boundaries (database calls, API calls, external services) |
| Comments | `///` for public API documentation; inline comments explain _why_, not _what_ |

---

## Cycle Options

| Option | Value | Description |
|---|---|---|
| auto_verify | `true` | Spawn verify agent during Phase 4A |
| auto_review | `true` | Spawn review agent during Phase 4A |
| feature_idea_on_empty | `true` | When /cycle has no args and no active state, offer to pull from FEATURES.md |


## Branch Configuration

| Field | Value |
|---|---|
| base_branch | main |
| feature_branch_pattern | feature/[short-description] |
| pr_target | main |

Agents and skills read `base_branch` when running git diffs and creating PRs. Update `pr_target` if your team's PR flow targets a different branch than `base_branch`.
