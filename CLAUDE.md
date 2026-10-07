# agent-sdlc — SDLC Framework Repo (workplace fork, omp target)

This repo contains the agent pipeline that gets deployed into projects. It is **language-agnostic**: the core is stack-neutral and stack-specific rules live in a **pack** (`.claude/packs/<lang>/`). The default active pack is **Flutter**; **.NET** ships as an alternate template. You are editing the **framework itself**, not an app — no app build/test commands apply here.

## Harness target

This branch (`feature/omp-openrouter`) targets **Oh My Pi (omp)** with models routed through **OpenRouter**. The `.omp/` directory is the native omp adapter layer; `.claude/` remains the source of truth for skills, packs, and the agent-readable runtime config (`.omp/agent-config.md`). See README § "omp + OpenRouter deployment" for the full setup.

## Structure

```
.omp/
  agents/         # 13 omp-native subagent definitions (frontmatter + body)
  config.yml      # omp harness settings (modelRoles, isolation, advisor, memory, etc.)
  models.yml.sample  # OpenRouter provider config + per-tier model menu
  mcp.json.sample    # Context Sources MCP template (omp format)
  agent-config.md # central runtime config — the one file users customize
  AGENTS.md       # project context (auto-loaded by omp, priority 100)
  RULES.md        # sticky hard rules (always-apply)
  hooks/
    log-event.ts  # supplementary telemetry hook
.claude/
  skills/         # skills (discovered by omp via claude provider, priority 80)
    cycle/        # the orchestrator (/cycle)
    project-conventions/  # ACTIVE stack conventions
    context-sources/      # MCP/RAG plug-in contract
  packs/          # swappable language packs (flutter, dotnet)
  agents/         # source-of-truth agent bodies (Claude Code path)
```

## Branching

Work merges **feature → develop → main**. `develop` is the integration branch; open PRs against it,
not against `main`. `main` is release, and reaching it is a separate, deliberate merge.

This was not followed before 2026-09-12 — PRs went straight to `main` and `develop` sat 150 commits
behind — so treat an existing branch cut from `main` as the exception, not the pattern.

## Editing guidelines

- Put **stack-specific** content in a pack (`.claude/packs/<lang>/`), never in a core agent/skill.
- Agent files in `.omp/agents/` — change behavior by editing the body.
- Skill files in `.claude/skills/` — `/cycle` and other entry-point skills.
- `.omp/agent-config.md` — the only file users customize per-project; keep it machine-readable (tables).
- When adding a new agent or skill, update README.md and the relevant sub-README.
- Internal framework R&D notes are archived under `docs/internal/`.
