# Per-project packs — design

Status: approved in conversation 2026-10-12, sections 1–4; this document is the written spec.
Branch: `feat/per-project-packs`, off `fix/windows-support`. Finding F26 in
`docs/internal/windows-support-plan.md` is the origin.

## Problem

The active pack is chosen per **framework checkout**, not per project. Activating a pack means
editing framework files that every project on the machine shares:

- `/setup` copies the pack's conventions into the `project-conventions` and `ui-test-patterns`
  skills, so the skills hold whichever stack was activated last.
- Each agent's `tools:` line names stack commands — today `Bash(flutter …)`, `Bash(dart …)` and
  `Bash(go …)`. No agent names `dotnet`.

So one checkout cannot serve a .NET repo and a Flutter repo, and switching a project to .NET
rewrites framework files the guard hook is there to protect. Under Claude Code the obvious
workaround — override the skill per project — is ruled out: skill precedence is personal
(`~/.claude/skills/`) over project, and the framework's skills are linked at personal scope.

## Goal

One framework checkout serves projects on different stacks. A project chooses its stack in its
own `.omp/agent-config.md`; nothing in the framework is edited to switch. Works under Claude Code
and keeps working under omp. Existing Flutter deployments see no behaviour change.

Out of scope: writing real .NET conventions (the dotnet pack's two remaining placeholders stay,
see Known gaps), new packs, and the .NET-flavour question (modern vs .NET Framework) — the design
takes each project's commands from its own config, so that question is answered per repo.

## Facts the design rests on

| Fact | Source |
|---|---|
| A `Bash(pattern)` entry in an agent's `tools:` is **not** a ceiling: an agent with `tools: Bash(echo *)` ran `touch`, confirmed by the file on disk. Permission rules are what deny. | Spike 2026-10-09, headless `claude -p --permission-mode dontAsk`; interactive mode assumed to match, not separately run |
| Session/project permission rules decide whether a Bash command runs: a non-allowed `touch` was denied with "don't ask mode" text, the file absent. | Same spike |
| Agent precedence: project `.claude/agents/` beats personal `~/.claude/agents/`. | Claude Code sub-agents docs, Scope & Locations |
| Skill precedence: personal `~/.claude/skills/` beats project `.claude/skills/`. | Claude Code skills docs, Skill Locations and Precedence |
| Agent and skill frontmatter is static; no variables or includes. | Claude Code docs |
| `config-get.py` already reads Project Commands rows (`config-get.py "Run all tests"` → `flutter test`). | Measured |
| `suite-result.py` and `symbol-refs.py` already read `active_pack` from the **project's** config. | Source |

## Design

### 1. Stack knowledge reaches agents at run time

- `project-conventions` and `ui-test-patterns` become **pointer skills**. Their body instructs:
  resolve the pack with `config-get.py active_pack --default flutter`, then read and follow
  `.claude/packs/<pack>/conventions.md` (respectively `ui-test-patterns.md`). The pack file is the
  only copy of the rules. A pack without `ui-test-patterns.md` is reported as such, not guessed.
- Every agent's `tools:` line, in `.claude/agents/` and `.omp/agents/` alike, replaces its
  stack-specific `Bash(…)` entries with a single plain `Bash`. Non-Bash tools are unchanged, so an
  agent that has no `Edit` still has none. Framework-script entries (`Bash(python3 .claude/…)`,
  `Bash(bash .claude/…)`) are left as they are — they are not stack-specific.
- The few agent and skill bodies that hard-code a stack command (`flutter analyze`, `dart format`)
  name the Project Commands row instead ("the **Analyze / lint** command").

### 2. Permissions come from the project's own commands

`deploy.sh grants <project>` gains a second source: the project's Project Commands table.

- Command rows: Run all tests, Run specific test file, Run single test by name, Analyze / lint,
  Format, Code generation. The other rows (CI workflow, Test path glob, Test anti-patterns) are
  not commands and produce nothing. An empty or absent row produces nothing.
- Each command row yields `Bash(<prefix>*)`, where the prefix is the command's leading words up to,
  not including, the first word that is a placeholder (`<…>`), a flag (`-…`), a path or glob
  (contains `/`, `\`, `.` as its first character, or `*`), or quoted. Examples:

  | Command | Rule |
  |---|---|
  | `dotnet test` | `Bash(dotnet test*)` |
  | `flutter test <path> --plain-name "<n>"` | `Bash(flutter test*)` |
  | `dart format .` | `Bash(dart format*)` |
  | `flutter pub run build_runner build --delete-conflicting-outputs` | `Bash(flutter pub run build_runner build*)` |

  Identical rules collapse to one.
- A compound row — containing `&&`, `||`, `;`, `|`, `` ` `` or `$(` — gets **no** rule. `grants`
  names the row and suggests wrapping it in a project script, rather than emitting a broad rule.
- Output: the project-command rules are printed under their own heading beside the existing
  framework, artifact and vault lines, narrowed to what the project's `settings.json` lacks, as
  `grants <project>` already does.
- `deploy.sh check` reports each missing project-command rule as `GRANT` and counts it, as it
  does for framework scripts.
- These are project-level rules. User-level and managed rules still apply; a deny anywhere wins.
  Under omp nothing changes: bash approval is `.omp/config.yml`'s.

### 3. `/setup` and the pack files

- `/setup` Step 7 "activate the pack" becomes: write `active_pack` into the project's config;
  seed its Project Commands table from `packs/<pack>/commands.md`; run `deploy.sh grants
  <project>` and show the lines to paste. It no longer copies anything into a skill.
- The dotnet pack gains a `commands.md` in the Flutter pack's shape, seeded with modern .NET
  defaults: `dotnet test`; `dotnet test <project>`; `dotnet test <project> --filter
  "FullyQualifiedName~<test name>"`; `dotnet format --verify-no-changes`; `dotnet format`; no code
  generation; `tests/**`; the pack's own `test-antipatterns.md`. Its notes say legacy projects
  override these rows.
- The header comments of each pack's `conventions.md` (and Flutter's `ui-test-patterns.md`) stop
  saying "`/setup` copies this body into the skill; keep the two in sync" and say this file is
  what agents read.
- `packs/README.md` § "How a pack becomes active" is rewritten to the three steps above; the steps
  that copied a body into a skill and edited agents' `tools:` are removed.

### 4. Compatibility

- A project with no `active_pack` row resolves to `flutter`, today's behaviour.
- An existing Flutter project already holds its stack grants in `settings.json`. `deploy.sh
  check` may name one it now expects; `deploy.sh grants <project>` prints it.

## Testing

Each change test-first, in the house style (stdlib, no network, a stub where a binary is needed):

1. Pointer skills — a fixture with `active_pack: dotnet` resolves to the dotnet conventions file;
   one without the row resolves to Flutter's. A structure test asserts the two skills hold no
   pack text, so they cannot become copies again.
2. Agent tools — a framework check fails if any agent in either directory names a stack-specific
   `Bash(…)` pattern; the existing harness-parity test keeps the directories in step.
3. `deploy.sh grants` — a .NET fixture yields `Bash(dotnet test*)` and `Bash(dotnet format*)`; a
   Flutter fixture its own; the three test rows collapse to one; a compound row is named and gets
   no rule; non-command and empty rows yield nothing; rules already held are not reprinted.
4. `deploy.sh check` — reports a missing project-command rule and fails; quiet once present.
5. Packs — every pack has a `commands.md` whose table has the six command rows and parses.
6. Full suite on Windows and on a WSL Linux clone.

## Rollout

- Separate PR from the Windows branch, mergeable right after it.
- Then the real run deferred from the Windows work (W10): a throwaway local .NET solution with
  xUnit tests, `active_pack: dotnet`, one lean `/cycle` end to end and a two-issue
  `/cycle --parallel`, stopping before push and PR and using `--no-claim`. It exercises Windows
  and per-project packs together and settles F23 (vault grant form on Windows).

## Known gaps

- The dotnet pack's `conventions.md` and `test-patterns.md` each still hold a template
  placeholder. Real .NET conventions are the team's to write; a project overrides them in its
  config regardless.
- The tools-is-not-a-ceiling fact was measured headless only.
