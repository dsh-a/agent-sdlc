# Sticky rules — agent-sdlc framework

Never commit `agent_states/`, `.claude/worktrees/`, or `cycle_reports/` — runtime artifacts covered by the managed .gitignore block.

Never edit generated files (`.g.dart`, `*.gen.dart`) — run the code generation command instead.

Never add packages without checking `pubspec.yaml` first.

Stack-specific content belongs in a pack (`.claude/packs/<lang>/`), never in a core agent or skill.

When passing `model:` to a task spawn, resolve the tier label (opus/sonnet/haiku) through the Model Versions table in `.omp/agent-config.md` and pass the specific model ID, not the alias label.

# Phase-specific rules (injected by omp's time-traveling stream rules)
# TTSR re-attaches these near the current turn so they stay visible after
# context growth. Each rule has a glob that scopes it to a specific phase.

## Phase 1: scope changes are NORMAL — the PRD is a draft; refine it

## Phase 2: do NOT re-open AC unless the task decomposition reveals a gap

## Phase 3: do NOT edit the PRD or task file (they are frozen at Gate 2)

## Phase 4A: do NOT implement fixes — only verify, review, and report
