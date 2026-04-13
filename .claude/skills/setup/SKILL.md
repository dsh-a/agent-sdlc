# Setup — Initial Configuration

You are helping a user configure the agent-sdlc pipeline for their project. Walk through each step interactively — ask questions, confirm choices, then generate the configuration.

---

## Step 1 — Detect project type

Inspect the project root:
- Read `package.json` for scripts, dependencies, and framework hints
- Check for `tsconfig.json`, framework config files (`next.config.js`, `vite.config.ts`, `nest-cli.json`, `angular.json`, etc.)
- Check for existing test configuration (`jest.config.*`, `vitest.config.*`, `.mocharc.*`, etc.)
- Check for linter configuration (`eslint.config.*`, `biome.json`, `.eslintrc.*`, etc.)
- Check for existing `.claude/config.md` — if it exists, inform the user and offer to update it or start fresh

Summarize findings to the user: framework, test runner, linter, type checker.

---

## Step 2 — Verify npm scripts

Check that these npm scripts exist in `package.json`:

| Script | Required | Purpose |
|---|---|---|
| `test` | Yes | Run tests |
| `lint` | Yes | Run linter |
| `typecheck` | Yes | Run type checker |
| `codegen` | No | Run code generation |

If any required scripts are missing, inform the user what to add and suggest values based on the detected toolchain (e.g., `"test": "vitest"` if vitest config exists).

Wait for the user to confirm scripts are in place before continuing.

---

## Step 3 — Configure architecture rules

Ask the user about their project's architecture:

1. **"What are your main source code layers?"**
   Offer common patterns as examples:
   - Domain / Data / UI (layered architecture)
   - Features / Shared / Core (feature-based)
   - Flat (no explicit layers)
   - Custom

2. **"What are the import rules between layers?"**
   For each layer identified, ask which other layers it may import from and which are forbidden.

3. **"What state management pattern do you use?"**
   Examples: React hooks + Context, Zustand, Redux, MobX, plain classes, none (server-only)

4. **"What DI / module registration pattern do you use?"**
   Examples: inversify, tsyringe, NestJS modules, manual factory, none

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

1. **File naming**: `kebab-case` (default), `camelCase`, `PascalCase`, `snake_case`
2. **Line length**: 100 (default), 80, 120, or custom
3. **Logging**: What logger does the project use? (e.g., winston, pino, console with wrapper, built-in)
4. **Comments**: `/** */` JSDoc (default) or project-specific convention

---

## Step 7 — Generate config file

Based on all answers, generate `.claude/config.md` following the structure of the existing template. If a config file already exists, show a diff of what would change and ask for confirmation before overwriting.

Write the file to `.claude/config.md`.

---

## Step 8 — Scaffold pattern discovery

Ask: **"Would you like to scan the codebase for recurring patterns to improve scaffold accuracy?"**

- If yes: run `/setup-scaffold` (follow the steps in `.claude/skills/setup-scaffold/SKILL.md`)
- If no: note that the scaffold agent will use GoF templates by default and can discover patterns on first use

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
  Scaffold:        [N pattern files created | using GoF templates]

Next steps:
  - Review .claude/config.md and adjust any values
  - Run /cycle to start your first feature cycle
  - Run /setup-scaffold later to discover project patterns
```
