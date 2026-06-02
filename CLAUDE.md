# agent-sdlc — SDLC Framework Repo (`company-a` fork)

This repo contains the agent pipeline that gets deployed into projects. It is **language-agnostic**: the core is stack-neutral and stack-specific rules live in a **pack** (`.claude/packs/<lang>/`). The default active pack is **.NET**; **Flutter** ships as a reference example. You are editing the **framework itself**, not an app — no app build/test commands apply here.

## Structure

```
.claude/
  agents/         # Subagent definitions (Markdown + YAML frontmatter), stack-neutral
    scaffold/     # Language-neutral pattern shapes for the scaffold agent
  skills/
    cycle/                # Main pipeline orchestrator (SKILL.md + templates)
    project-conventions/  # ACTIVE stack conventions (populated from a pack)
    context-sources/      # MCP/RAG plug-in contract
    ...                   # One subdirectory per skill
  packs/          # Swappable language packs (dotnet, flutter)
  config.md       # Active pack, model allocation, project commands, context sources, …
  .mcp.json.sample  # Template for connecting MCP servers
README.md         # Setup and usage documentation (+ sub-READMEs under .claude/, docs/)
```

## Editing this fork — keep the core stack-neutral

- Put **stack-specific** content in a pack (`.claude/packs/<lang>/`), never in a core agent/skill. Core files read commands/paths from `config.md` and defer conventions to the `project-conventions` skill.
- **Context Sources** (MCP/RAG plug-ins) are config-driven — adding one is a `config.md` row + a connected MCP, no code changes. See `.claude/skills/context-sources/SKILL.md`.
- The agent `tools:` frontmatter and `.claude/settings.json` permissions are **not** config-driven and must be hand-aligned with the toolchain.

## Key files

- `.claude/config.md` — central config read by `/cycle` at runtime: model preset, effort levels, artifact paths, optional agents, branch rules
- `.claude/skills/cycle/SKILL.md` — the orchestrator; this is what runs when a user invokes `/cycle`
- `.claude/agents/*.md` — spawned by the orchestrator during Phase 3+

## Pipeline phases (for context)

```
Phase 1A  PRD creation       create-prd agent
Phase 1C  Gate 1             user approves PRD
Phase 2   Task generation    generate-tasks agent
Phase 2B  Gate 2             user approves tasks
Phase 3   Implementation     parallel agents in isolated worktrees
Phase 4A  Wrap-up            final tests, cycle report, run report, verify/review
Phase 4B  Release            push branch, open PR
```

## Editing guidelines

- Agent files in `.claude/agents/` — change behavior by editing the system prompt body
- Skill files in `.claude/skills/` — `/cycle` and other entry-point skills; `disable-model-invocation: true` means they only load when explicitly invoked
- `config.md` — the only file users are expected to customize per-project; keep it machine-readable (tables, not prose)
- When adding a new agent or skill, update `README.md`'s "What's included" table and the relevant sub-README (`.claude/agents/README.md` or `.claude/skills/README.md`)
- Internal framework R&D notes are archived under `docs/internal/` — keep workplace-facing docs (`README.md`, `docs/WORKPLACE-SETUP.md`, `docs/CONTEXT-SOURCES.md`) at the top level

## Deployment

Users copy `.claude/` from this repo into their project root. There is no build step.
