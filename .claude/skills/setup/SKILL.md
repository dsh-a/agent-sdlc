---
disable-model-invocation: true
---

# Setup — Initial Configuration

You are helping a user configure the agent-sdlc pipeline for their project. The pipeline is
**language-agnostic**; a *pack* supplies the conventions for one stack. Walk through each
step interactively — ask questions, confirm choices, then generate the configuration.

---

## Step 1 — Detect project type and select a pack

Inspect the project root to identify the stack:

| Signal | Pack |
|---|---|
| `*.sln`, `*.csproj`, `Directory.Build.props` | `dotnet` |
| `pubspec.yaml` | `flutter` |
| `package.json` (+ `tsconfig.json`) | author a `node`/`typescript` pack |
| something else | author a new pack (`.claude/packs/README.md`) |

- List the available packs under `.claude/packs/`.
- Read the relevant manifest(s) for dependencies, framework version, and tooling.
- Detect the test framework, linter/analyzer, and any codegen step.
- Check for an existing `.claude/config.md` — if present, offer to update it or start fresh.

Summarize findings, then confirm the **Active Pack** with the user. If no matching pack
exists, offer to scaffold one by copying `.claude/packs/dotnet/` and filling it in.

## Step 2 — Verify project commands

Confirm the build/test/analyze commands for the stack. Defaults for `flutter`:

| Purpose | Command |
|---|---|
| Run all tests | `flutter test` |
| Run specific test file | `flutter test <path>` |
| Analyze / lint | `flutter analyze` |
| Code generation | `flutter pub run build_runner build --delete-conflicting-outputs` |
| Test path glob | `test/**` |

Ask the user to confirm or correct each, plus the **Test path glob** and **Test
anti-patterns** file (defaults to the active pack's). Wait for confirmation before continuing.

## Step 3 — Configure architecture rules

Ask about the project's architecture:

1. **"What are your main source layers?"** — offer common shapes (Clean/Onion: Domain /
   Application / Infrastructure / Presentation; Vertical slices; Flat). Capture path patterns.
2. **"What are the import rules between layers?"** — for each layer, which others it may
   import from and which are forbidden. Remind: the domain layer should be pure (no framework/IO).
3. **"What presentation / state-management pattern do you use?"** — e.g. MVC controllers,
   Minimal APIs, MVVM, Blazor components, CQRS handlers.
4. **"What DI pattern do you use?"** — e.g. built-in `IServiceCollection`, Autofac, manual factory.

Fill in § Layer Boundaries, § Pattern Compliance, and § Convention Checks of `config.md`.

## Step 4 — Choose model preset

- **personal** — mostly sonnet for implementation, haiku for lightweight tasks. Balanced. Default.
- **team** — similar with a few upgrades.
- **enterprise** — opus for planning/review agents, sonnet for implementation. Highest quality, higher cost.

Ask the user to choose; they can override individual agent models later.

## Step 5 — Configure optional agents

Ask: **"Should `/cycle` automatically run code review and verification after implementation?"**
Default both enabled. Explain that when disabled, the cycle recommends running them manually.

## Step 6 — Configure Context Sources (MCP / RAG plug-in points)

Ask whether the team has external knowledge sources to wire in (a documentation MCP, a
codebase-analysis / RAG service, an ADR store). For each:

1. **id** and **type** (`mcp` / `skill`) and the tool/skill name.
2. **consult_at** stages — `prd`, `tasks`, `predigest`, `implement`, `review`, `verify`.
3. **required** — `optional` (default) or `required` (never for an unreleased source).
4. **enabled** — `false` until the MCP server is actually connected in `.claude/.mcp.json`.
5. a **query_hint**.

Write these as rows in `config.md` § Context Sources, and remind the user to connect the
servers in `.claude/.mcp.json` (template `.claude/.mcp.json.sample`) and to add the matching
`mcp__<id>__*` permission in `.claude/settings.json`. See `.claude/skills/context-sources/SKILL.md`
and `docs/CONTEXT-SOURCES.md`.

## Step 7 — Generate config + activate the pack

1. Generate `.claude/config.md` from all answers, following the existing template's structure
   (Active Pack, Project Commands, Architecture Review Rules, Context Sources, model preset,
   optional agents). If a config exists, show a diff and confirm before overwriting.
2. **Activate the pack:** copy `.claude/packs/<active_pack>/conventions.md` body into
   `.claude/skills/project-conventions/SKILL.md` (preserve its frontmatter), and the pack's
   `ui-test-patterns.md` into `.claude/skills/ui-test-patterns/SKILL.md` if present.

## Step 8 — Update permissions

Remind the user to align `.claude/settings.json` Bash allowlist with the chosen toolchain
(e.g. `Bash(flutter test*)`, `Bash(flutter analyze*)`) and add any `mcp__<source>__*` entries.
(The agent cannot self-edit `settings.json` — the user applies this.)

## Step 9 — Scaffold pattern discovery

Ask: **"Scan the codebase for recurring patterns to improve scaffold accuracy?"**
- Yes → run `/setup-scaffold`.
- No → the scaffold agent uses the language-neutral pattern shapes + the active pack's
  `scaffold-snippets.md`, and can discover patterns on first use.

## Step 10 — Summary

```
Configuration complete:

  Config file:     .claude/config.md
  Active pack:     [flutter | dotnet | ...]
  Model preset:    [personal | team | enterprise]
  Architecture:    [layers summary]
  Auto verify:     [enabled | disabled]
  Auto review:     [enabled | disabled]
  Context sources: [N configured — M enabled]
  Scaffold:        [N pattern files created | using pack defaults]

Next steps:
  - Review .claude/config.md and adjust any values
  - Connect MCP servers in .claude/.mcp.json and update settings.json permissions
  - Run /cycle to start your first feature cycle
```
