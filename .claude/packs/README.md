# Language packs

A **pack** is the swappable, language/framework-specific layer of this pipeline. The core
(orchestrator, agents, skills) is language-agnostic; a pack supplies the conventions, test
patterns, and code idioms for one stack.

```
packs/
  flutter/   ← default active pack (the framework's Flutter content)
  dotnet/    ← alternate template (placeholders — fill via /setup, or copy to author a new pack)
```

## What a pack contains

| File | Feeds | Purpose |
|---|---|---|
| `conventions.md` | the active `project-conventions` skill | layer boundaries, member order, naming, logging, entity construction |
| `test-patterns.md` | the `test` agent / skill | framework, fixtures, naming, async rules |
| `test-antipatterns.md` | the cycle silent-skip gate | regexes that block a merge (gated/swallowed/skipped assertions) |
| `scaffold-snippets.md` | the `scaffold` agent | language idiom for each pattern shape |

## How a pack becomes active

There is no runtime indirection — agents load the **`project-conventions` skill**
deterministically via their `skills:` frontmatter. "Switching packs" means populating that
skill (and the agent tool surface) from a pack:

1. Set **Active Pack** in `.claude/config.md` (informational + used by `/setup`).
2. Copy `packs/<lang>/conventions.md` body → `.claude/skills/project-conventions/SKILL.md`
   (keep its frontmatter). `/setup` does this for you.
3. Point the cycle silent-skip gate at `packs/<lang>/test-antipatterns.md` (config
   § Project Commands → *Test anti-patterns*).
4. Update each agent's `tools:` frontmatter to the pack's build/test/format commands
   (this is static per-agent and cannot be config-driven — see `.claude/agents/README.md`).
5. Update `.claude/config.md` § Project Commands and `.claude/settings.json` Bash allowlist.

## Authoring a new pack

Copy `packs/dotnet/` to `packs/<lang>/`, fill in the four files using `packs/flutter/` as a
complete worked example, then run the switch steps above. Keep `conventions.md` as the
canonical source and re-run `/setup` after edits so the active skill stays in sync.
