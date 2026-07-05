# `.claude/` — layout and the core-vs-pack model

Everything the pipeline needs lives here. Copy this directory into a project root to install
the pipeline.

```
.claude/
  config.md            # central runtime config — the one file you customize
  settings.json        # Bash/MCP permissions + telemetry hooks
  settings.json.sample # hooks template to merge into settings.json
  .mcp.json.sample     # template for connecting MCP servers (Context Sources)
  hooks/
    log-event.py       # per-agent event log (PostToolUse + SubagentStop)
  agents/              # the agent team (stack-neutral) — see agents/README.md
    scaffold/          # language-neutral pattern shapes (interface, service, command, …)
  skills/              # skills — see skills/README.md
    project-conventions/  # ACTIVE stack conventions (loaded by agents)
    ui-test-patterns/     # ACTIVE UI test patterns (loaded by agents)
    context-sources/      # the MCP/RAG plug-in contract
    cycle/                # the orchestrator (/cycle)
  packs/               # swappable language packs — see packs/README.md
    dotnet/  flutter/
```

## The two layers

**Core (stack-neutral).** The orchestrator, agents, and most skills carry no language
assumptions. They read commands, paths, and rules from `config.md` and load conventions from
the `project-conventions` skill.

**Pack (stack-specific).** A pack supplies the conventions, test patterns, anti-patterns, and
code idioms for one stack. The **active** conventions are loaded deterministically from the
`project-conventions` skill (via each agent's `skills:` frontmatter); a pack is the
swappable source you populate that skill from. Default active pack: **dotnet**. See
[`packs/README.md`](packs/README.md).

## What reads what

| Component | Reads from `config.md` |
|---|---|
| `cycle/SKILL.md` (orchestrator) | every section — at ~25 lookup points |
| Implementation agents | Model Allocation, Project Commands (via the orchestrator) |
| `review` / `verify` | Architecture Review Rules, Branch Configuration, Context Sources |
| Silent-skip gate | Project Commands → Test path glob + Test anti-patterns |

## Two things the agent can't self-configure

- **`settings.json` permissions** — the harness blocks an agent from widening its own
  permissions. A human edits this to match the toolchain and add `mcp__<source>__*` entries.
- **Agent `tools:` frontmatter** — static per-agent (it can't be config-driven). Switching
  the build/test toolchain means editing the `Bash(...)` tokens in the agent files. See
  [`agents/README.md`](agents/README.md).
