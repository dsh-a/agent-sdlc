# Setup — Initial Configuration

You are helping a user configure the agent-sdlc pipeline for their Flutter/Dart project. Walk through each step interactively — ask questions, confirm choices, then generate the configuration.

---

## Step 1 — Detect project type

Inspect the project root:
- Read `pubspec.yaml` for dependencies, Flutter SDK constraint, and dev dependencies
- Check for `analysis_options.yaml` — note any lint rules or custom analyzer settings
- Check for test configuration (`flutter_test` in dev_dependencies, any `test/` directory structure)
- Check for code generation (`build_runner`, `freezed`, `json_serializable`, `drift`, `riverpod_generator`, etc. in dev_dependencies)
- Check for existing state management packages (`provider`, `riverpod`, `bloc`, `get`, `mobx`, etc.)
- Check for existing `.claude/config.md` — if it exists, inform the user and offer to update it or start fresh

Summarize findings to the user: Flutter version constraint, state management, codegen tools, key packages.

---

## Step 2 — Verify Flutter commands

Check that these commands are usable for the project:

| Command | Required | Purpose |
|---|---|---|
| `flutter test` | Yes | Run tests |
| `flutter analyze` | Yes | Run static analysis |
| `flutter pub run build_runner build` | If codegen detected | Run code generation |
| `dart run` | No | Run Dart scripts |

If `analysis_options.yaml` is missing or minimal, suggest adding one based on `package:flutter_lints` or `package:very_good_analysis`.

Wait for the user to confirm the toolchain is in place before continuing.

---

## Step 3 — Configure architecture rules

Ask the user about their project's architecture:

1. **"What are your main source code layers?"**
   Offer common Flutter patterns as examples:
   - Domain / Data / UI (clean architecture)
   - Feature-based (each feature has its own domain/data/ui subfolders)
   - Flat (no explicit layers)
   - Custom

2. **"What are the import rules between layers?"**
   For each layer identified, ask which other layers it may import from and which are forbidden.
   Remind: domain layer should be pure Dart — no Flutter imports.

3. **"What state management pattern do you use?"**
   Examples: MVVM with ChangeNotifier + Provider, Riverpod, BLoC, GetX, MobX, plain setState

4. **"What DI / dependency injection pattern do you use?"**
   Examples: Provider/MultiProvider, get_it, Riverpod providers, manual factory, none

Fill in the Architecture Review Rules section of config.md based on answers.

---

## Step 4 — Choose model preset

Explain the presets:

- **personal** — Mostly sonnet for implementation, haiku for lightweight tasks (pre-digest, monitor, adversarial testing). Good balance of cost and quality. Default.
- **enterprise** — Opus for planning and review agents (create-prd, generate-tasks, verify, review, self-improve), sonnet for implementation. Highest quality, higher cost.

Ask the user to choose. They can also customize individual agent models after setup.

---

## Step 5 — Configure optional agents

Ask: **"Should `/cycle` automatically run code review and verification after implementation?"**

- Default: both enabled
- User can disable either or both
- Explain: when enabled, verify and review agents run autonomously during Phase 4A. When disabled, the cycle recommends running them manually.

---

## Step 6 — Convention checks

Ask about code conventions, offering detected defaults where possible:

1. **File naming**: `snake_case` (Dart default)
2. **Line length**: 100 (default), 80, 120, or custom
3. **Logging**: What logger does the project use? (e.g., `package:logging`, custom wrapper, `debugPrint`)
4. **Comments**: `///` Dart doc comments (default) or project-specific convention
5. **Private members**: Leading underscore convention (Dart default)

---

## Step 7 — Generate config file

Based on all answers, generate `.claude/config.md` following the structure of the existing template. If a config file already exists, show a diff of what would change and ask for confirmation before overwriting.

Write the file to `.claude/config.md`.

---

## Step 8 — Scaffold pattern discovery

Ask: **"Would you like to scan the codebase for recurring patterns to improve scaffold accuracy?"**

- If yes: run `/setup-scaffold` (follow the steps in `.claude/skills/setup-scaffold/SKILL.md`)
- If no: note that the scaffold agent will use the default Dart/Flutter pattern templates and can discover patterns on first use

---

## Step 9 — Summary

Present what was configured:

```
Configuration complete:

  Config file:     .claude/config.md
  Model preset:    [personal|enterprise]
  Architecture:    [layers summary]
  State mgmt:      [pattern]
  DI pattern:      [pattern]
  Auto verify:     [enabled|disabled]
  Auto review:     [enabled|disabled]
  Scaffold:        [N pattern files created | using default templates]

Next steps:
  - Review .claude/config.md and adjust any values
  - Run /cycle to start your first feature cycle
  - Run /setup-scaffold later to discover project-specific patterns
```
