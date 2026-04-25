# agent-sdlc — SDLC Framework Repo

This repo contains the agent pipeline that gets deployed into Flutter/Dart projects. You are editing the **framework itself**, not a Flutter app — `flutter test` and `flutter analyze` do not apply here.

## Structure

```
.claude/
  agents/         # Subagent definitions (Markdown + YAML frontmatter)
    scaffold/     # Pattern templates for the scaffold agent
  skills/
    cycle/        # Main pipeline orchestrator (SKILL.md + templates)
    ...           # One subdirectory per skill
  config.md       # Model allocation, effort, artifact paths, cycle options
README.md         # Setup and usage documentation
```

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
- When adding a new agent or skill, update `README.md`'s "What's included" table

## Deployment

Users copy `.claude/` from this repo into their project root. There is no build step.
