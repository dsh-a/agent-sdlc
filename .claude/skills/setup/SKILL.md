---
name: setup
description: Interactive configuration wizard for the agent-sdlc pipeline. Detects the project stack, selects a language pack, generates .omp/agent-config.md (Project Commands, Architecture Rules, Context Sources, model preset), seeds the project's instruction file with the pack's conventions, and sets up its permissions.
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
- Check for an existing `.omp/agent-config.md` — if present, offer to update it or start fresh.

Summarize findings, then confirm the **Active Pack** with the user. If no matching pack
exists, offer to scaffold one by copying `.claude/packs/dotnet/` and filling it in.

## Step 2 — Verify project commands

Confirm the build/test/analyze commands for the stack. Take the defaults from
`.claude/packs/<active_pack>/commands.md` and show them as a table.

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

Fill in § Layer Boundaries, § Pattern Compliance, and § Convention Checks of `.omp/agent-config.md`.

## Step 4 — Choose model preset

- **personal** — mostly sonnet for implementation, haiku for lightweight tasks. Balanced. Default.
- **team** — similar with a few upgrades.
- **enterprise** — opus for planning/review agents, sonnet for implementation. Highest quality, higher cost.

Ask the user to choose; they can override individual agent models later.

## Step 5 — Configure optional agents

Ask: **"Should `/cycle` automatically run code review and verification after implementation?"**
Default both enabled. Explain that when disabled, the cycle recommends running them manually.

Leave `agent_skills` in § Cycle Options `false` unless the user asks for it. Mention it in the
summary: `true` makes each agent read the skills its instructions name, at the cost of that text in
its context for the whole run.

### Partial checkout for parallel cycles

`sparse_clones` in § Cycle Options makes each `/cycle --parallel` slot check out only the
directories its story's `## Slices` name. It is off by default. Before offering it, show the
repository's tracked file count and size:

```sh
git ls-files | wc -l
git ls-tree -r -l HEAD | awk '{s += $4} END {printf "%.1f MB\n", s / 1048576}'
```

Then read out its risks:

- A build or test that needs a file outside the slot's set fails, and in .NET the error can look
  unrelated to the missing file. `run-suite.sh` names the directory to add.
- Cross-cutting changes the story did not predict are not visible to the agents.
- IDE tooling opened on a slot sees part of the solution.
- New slots are made with `git worktree add`, so omp's whole-tree copy (warm caches, `.env`) is
  not used.
- Turning it on sets `extensions.worktreeConfig` in the repository's git config, where it stays
  after the option is turned off. Older libgit2-based tools (some IDE git integrations and GUI
  clients) may refuse such a repository. Once no slot is sparse,
  `git config --unset extensions.worktreeConfig` in the primary checkout removes it.

Ask: **"Enable partial checkout for parallel cycles? [y/N]"** The default answer is no. Set
`sparse_clones` to `true` only on an explicit yes; any other answer leaves it `false`. On yes, ask
for `always_checkout`: the directories every slot needs whatever its story names (solution and
build-props directories, shared libraries, CI files), comma-separated, or `none`.

## Step 6 — Configure Context Sources (MCP / RAG plug-in points)

Ask whether the team has external knowledge sources to wire in (a documentation MCP, a
codebase-analysis / RAG service, an ADR store). For each:

1. **id** and **type** (`mcp` / `skill`) and the tool/skill name.
2. **consult_at** stages — `prd`, `tasks`, `predigest`, `implement`, `review`, `verify`.
3. **required** — `optional` (default) or `required` (never for an unreleased source).
4. **enabled** — `false` until the MCP server is actually connected in `.omp/mcp.json`.
5. a **query_hint**.

Write these as rows in `.omp/agent-config.md` § Context Sources, and remind the user to connect the
servers in `.omp/mcp.json` (template `.omp/mcp.json.sample`). Under omp, MCP tools are
auto-discovered — no permission allowlist needed. See `.claude/skills/context-sources/SKILL.md`
and `docs/CONTEXT-SOURCES.md`.

## Step 7 — Generate config, conventions and permissions

1. Generate `.omp/agent-config.md` from all answers, following the existing template's structure
   (Active Pack, Project Commands, Architecture Review Rules, Context Sources, model preset,
   optional agents). If a config exists, show a diff and confirm before overwriting.
2. **Conventions:** offer `.claude/packs/<active_pack>/conventions.md` and the pack's
   test-patterns file as sections of the project's instruction file (`CLAUDE.md` under Claude
   Code, `AGENTS.md` under omp). Show what will be added, take a confirmation, and write it to
   the project. Skip a section the file already covers. Write nothing into the framework.
3. **Permissions (Claude Code):** run `bash <framework>/deploy.sh grants <project>` and show the
   lines. It names any Project Commands row it gives no rule; offer to put such a row in a
   project script. It also names the hook wiring the project lacks. On confirmation run
   `bash <framework>/deploy.sh grants --apply <project>`, which writes both.
   Skip this under omp.

## Step 8 — Confirm omp settings

Remind the user that `.omp/config.yml` controls bash approval (`tools.approval.bash: allow`),
task isolation, model roles, and other omp harness settings. The framework defaults are
sensible for most projects — adjust only if needed (e.g., `task.maxConcurrency` for a
smaller machine, `advisor.enabled: true` for complex cycles). No per-pattern Bash allowlist
is needed under omp (unlike Claude Code's `.claude/settings.json`).

## Step 9 — Scaffold pattern discovery

Ask: **"Scan the codebase for recurring patterns to improve scaffold accuracy?"**
- Yes → run `/setup-scaffold`.
- No → the scaffold agent uses the language-neutral pattern shapes + the active pack's
  `scaffold-snippets.md`, and can discover patterns on first use.

## Step 10 — Repository workflows (optional)

Ask: **"Install the framework's GitHub workflows into this repository?"**

List what is available first — `bash <framework>/install-workflows.sh list` — and what each
one costs. Today there is one:

| Template | Does | Costs |
|---|---|---|
| `review-comment-to-issue.yml` | `/bug`, `/story`, `/feature` at the start of a line in a PR comment files a labelled issue and replies with its number | seconds of Actions time per comment |

- Yes → `bash <framework>/install-workflows.sh install .`
- No → print that command so the decision is reversible without re-running setup.

**Offer; do not install by default.** This writes to `.github/`, changes what runs on the
project's pull requests, and spends their Actions minutes. None of that should happen because
a default said so.

Two things the installer reports that are worth reading aloud to the user, because both fail
silently in production:

- An `issue_comment` workflow runs from the repository's **default branch only**. If the
  default is `main` and cycles merge to `develop`, it will not fire until it reaches `main`,
  and nothing will say so.
- Board placement needs a `PROJECT_TOKEN` secret, because Projects v2 is user-scoped and
  `GITHUB_TOKEN` cannot write to it. Without it, issues are still filed and labelled and the
  workflow reports board placement as skipped.

## Step 11 — Summary

```
Configuration complete:

  Config file:     .omp/agent-config.md
  omp settings:    .omp/config.yml
  Active pack:     [flutter | dotnet | ...]
  Model preset:    [personal | team | enterprise]
  Architecture:    [layers summary]
  Auto verify:     [enabled | disabled]
  Auto review:     [enabled | disabled]
  Partial checkout: [off | on — always_checkout: ...]
  Context sources: [N configured — M enabled]
  Scaffold:        [N pattern files created | using pack defaults]
  Workflows:       [N installed | offered, not installed]

Next steps:
  - Review .omp/agent-config.md and .omp/config.yml and adjust any values
  - Copy .omp/models.yml.sample → ~/.omp/agent/models.yml and pick your OpenRouter models
  - Connect MCP servers in .omp/mcp.json
  - Run /cycle to start your first feature cycle
```
