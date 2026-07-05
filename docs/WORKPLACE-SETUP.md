# Workplace setup — onboarding guide

This walks a new engineer from zero to a first `/cycle` run on the `company-a` fork. The
pipeline is language-agnostic; the default active pack is **.NET**.

---

## 0. Prerequisites

- [Claude Code](https://claude.com/claude-code) installed and authenticated.
- `python3` on PATH (for the telemetry hooks — built-in on macOS/Linux).
- Your project is a git repository.
- Access to the team's MCP servers (e.g. `company-a-docs`) if you intend to wire them in.

---

## 1. Install the pipeline

From the fork, copy the `.claude/` directory into your project root:

```bash
cp -r /path/to/agent-sdlc/.claude/ /path/to/your-project/.claude/
```

This brings the orchestrator, the agent team, the skills, and the **packs**
(`.claude/packs/dotnet`, `.claude/packs/flutter`).

---

## 2. Run `/setup`

In Claude Code, from your project root:

```
/setup
```

The wizard:

1. **Detects your stack** (`*.sln`/`*.csproj` → dotnet, `pubspec.yaml` → flutter,
   `package.json` → node) and confirms the **Active Pack**.
2. Confirms **Project Commands** — build, test, run-one-test, analyze/lint, the **Test path
   glob**, and the **Test anti-patterns** file.
3. Captures **Architecture Review Rules** — your layers, import rules, presentation pattern, DI.
4. Asks about **Context Sources** (step 4 below).
5. Generates `.claude/config.md` and **populates** `project-conventions` from the pack.

You can re-run `/setup` any time, or edit `.claude/config.md` directly — it is the single
source of customization.

---

## 3. Fill in your .NET conventions

The default `dotnet` pack ships **placeholders**. Open
`.claude/skills/project-conventions/SKILL.md` (the active conventions) and fill in:

- **Layer boundaries** — real path patterns + allowed/forbidden imports (also mirror these in
  `.claude/config.md` § Layer Boundaries, which the `review` agent enforces).
- **Test framework** — xUnit / NUnit / MSTest and your mocking library, in
  `.claude/packs/dotnet/test-patterns.md`.
- **Test anti-patterns** — confirm the regexes in
  `.claude/packs/dotnet/test-antipatterns.md` match your framework (these block merges on
  gated/swallowed/skipped assertions — getting them wrong silently disables the gate).

The `flutter` pack (`.claude/packs/flutter/`) is a complete worked example to copy structure from.

---

## 4. Wire in MCP context sources (optional, recommended)

1. Copy the template: `cp .claude/.mcp.json.sample .claude/.mcp.json` and fill in your
   servers (replace each `REPLACE_ME`). **Gitignore `.claude/.mcp.json`** — it may carry creds.
2. Declare each source in `.claude/config.md` § Context Sources with the stages it should be
   consulted at and `enabled: true`.
   - `company-a-docs` ships enabled at `prd, tasks, implement, review`.
   - `codebase-rag` ships **disabled** — leave it off until the service is released.
3. See [`CONTEXT-SOURCES.md`](CONTEXT-SOURCES.md) for the full contract.

---

## 5. Apply permissions (you must do this — the agent can't)

The harness blocks an agent from widening its own permissions, so **you** edit
`.claude/settings.json`:

- Bash allowlist for your toolchain, e.g.:
  `Bash(dotnet test*)`, `Bash(dotnet build*)`, `Bash(dotnet format*)`, `Bash(dotnet restore*)`,
  `Bash(dotnet ef*)`, `Bash(git *)`, `Bash(gh pr*)`.
- One entry per context source: `mcp__company-a-docs__*` (and `mcp__codebase-rag__*` when released).

Keep the existing `hooks` block (telemetry) intact.

---

## 6. First cycle

```
/cycle Add CSV export to the reports page
```

This runs **dry-run** by default: it produces a PRD, generates tasks, and presents a plan
before implementing anything. Approve at Gate 1 ("Proceed to tasks?") and Gate 2 ("Begin
implementation?"). Add `--exe` to execute straight through after planning.

After Phase 4A, check the run report in `agent_tasks/reports/` (or your docs vault) — it
includes a **Context Sources** section showing which sources were consulted or degraded.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Agents prompt for permission on `dotnet …` | Add the Bash pattern to `.claude/settings.json` (step 5) |
| `context-source <id>: unavailable` in the report | The MCP isn't connected — check `.claude/.mcp.json` and the `mcp__<id>__*` permission |
| Conventions feel Flutter-y | The active pack/`project-conventions` wasn't populated — re-run `/setup` step 7 or copy from `packs/dotnet/conventions.md` |
| Silent-skip gate never fires | The **Test anti-patterns** regexes don't match your framework — fix `packs/dotnet/test-antipatterns.md` |
| Telemetry "not collected" in reports | Ensure the `hooks` block is in `settings.json` and `python3` is on PATH |
