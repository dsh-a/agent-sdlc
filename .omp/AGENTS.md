# agent-sdlc — omp + OpenRouter target

This repo contains the agent pipeline that gets deployed into projects. It is
language-agnostic: the core is stack-neutral and stack-specific rules live in a
**pack** (`.claude/packs/<lang>/`). The default active pack is **flutter**.

## omp layout

```
.omp/
  agents/            # 13 omp-native subagent definitions (frontmatter + body)
  config.yml         # omp harness settings (modelRoles, isolation, advisor, memory, retry, task, compaction)
  models.yml.sample  # OpenRouter provider config + per-tier model menu → copy to ~/.omp/agent/models.yml
  mcp.json.sample    # Context Sources MCP template → copy to .omp/mcp.json
  AGENTS.md          # this file — project context (auto-loaded by omp)
  RULES.md           # sticky hard rules (auto-loaded, always-apply)
  hooks/
    log-event.ts     # supplementary telemetry hook (native transcripts are primary)
```

## Where things live (hybrid — mid-migration to omp-native)

- **Agents** — `.omp/agents/` (omp-native frontmatter; bodies sourced from `.claude/agents/`)
- **Skills** — `.claude/skills/` (discovered by omp via the `claude` provider, priority 80)
- **Packs** — `.claude/packs/` (language-specific conventions + test anti-patterns)
- **Runtime config** — `.omp/agent-config.md` (model tiers, project commands, architecture rules, context sources — agents read it by path)
- **omp settings** — `.omp/config.yml` (modelRoles → OpenRouter, native isolation, advisor, memory, retry/fallback, task concurrency, compaction, autolearn, thinking budgets)

## Model tiers → OpenRouter

Three tiers map to omp roles:
- **opus** → `slow` role (orchestrator, verify, review)
- **sonnet** → `default` / `task` role (implementation agents)
- **haiku** → `smol` role (monitor, preflight, supervisor)

Pick your OpenRouter model per tier in `.omp/models.yml.sample` (copy to
`~/.omp/agent/models.yml`). `modelRoles` in `.omp/config.yml` reference canonical
tier ids; the `equivalence.overrides` block maps your OpenRouter picks to those
canonical ids.

## Pipeline phases

```
Phase 1A  PRD creation       create-prd agent
Phase 1C  Gate 1             user approves PRD
Phase 2   Task generation    generate-tasks agent
Phase 2B  Gate 2             user approves tasks
Phase 3   Implementation     parallel isolated agents (omp native isolation + batch spawns + irc whispers)
Phase 4A  Wrap-up            final tests, cycle report, verify/review
Phase 4B  Release            push branch, open PR
```

## Editing guidelines

- Stack-specific content goes in a pack (`.claude/packs/<lang>/`), never in a core agent/skill.
- Agent files in `.omp/agents/` — change behavior by editing the body (sourced from `.claude/agents/`).
- Skill files in `.claude/skills/` — `/cycle` and other entry-point skills.
- `.omp/agent-config.md` — the only file users customize per-project; keep it machine-readable (tables).
- When adding a new agent or skill, update README.md and the relevant sub-README.
