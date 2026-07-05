# Sticky rules — agent-sdlc framework

Never commit `agent_states/`, `.claude/worktrees/`, or `cycle_reports/` — runtime artifacts covered by the managed .gitignore block.

Never edit generated files (`.g.dart`, `*.gen.dart`) — run the code generation command instead.

Never add packages without checking `pubspec.yaml` first.

Stack-specific content belongs in a pack (`.claude/packs/<lang>/`), never in a core agent or skill.

When passing `model:` to a task spawn, resolve the tier label (opus/sonnet/haiku) through the Model Versions table in `.claude/config.md` and pass the specific model ID, not the alias label.
