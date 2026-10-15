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
| `conventions.md` | starter text for the project's instruction file | layer boundaries, member order, naming, logging, entity construction |
| `commands.md` | seeds `.omp/agent-config.md` § Project Commands | the stack's build/test/lint/codegen command defaults |
| `test-patterns.md` / `ui-test-patterns.md` | starter text for the project's instruction file | framework, fixtures, naming, async rules (filename varies by pack) |
| `test-antipatterns.md` | the cycle silent-skip gate | regexes that block a merge (gated/swallowed/skipped assertions) |
| `scaffold-snippets.md` | the `scaffold` agent | **index** of language idioms — a § Coverage table routing each pattern shape to one file in `snippets/`, plus the fallback for uncovered shapes |
| `snippets/<pattern>.md` | the `scaffold` agent | one Dart/C# idiom per pattern shape, named to match `.claude/agents/scaffold/<pattern>.md`. Each declares **extracted** (project house convention) or **illustrative** (reference only) |
| `sparse_closure.py` *(optional)* | `cycle/sparse-set.py` | `closure(dirs, tracked, read)`: directories a partial checkout must add for the set to build. `dotnet` adds the `ProjectReference` closure |

## How a project takes a pack

A pack is chosen per project. `/setup` runs these steps; nothing in the framework is edited.

1. Set **Active Pack** in the project's `.omp/agent-config.md`.
2. Seed § Project Commands from `packs/<lang>/commands.md`, then correct each row for the project.
3. Add `packs/<lang>/conventions.md` and the pack's test-patterns file to the project's
   instruction file (`CLAUDE.md`, `AGENTS.md`). Edit them there: the project's copy is what
   agents follow.
4. Point the cycle silent-skip gate at `packs/<lang>/test-antipatterns.md` (§ Project Commands →
   *Test anti-patterns*).
5. Grant the project's commands and wire the hooks. Claude Code:
   `deploy.sh grants --apply <project>`. omp: `.omp/config.yml` (`tools.approval.bash: allow`).

## Authoring a new pack

Copy `packs/dotnet/` to `packs/<lang>/` and fill in the files above, using `packs/flutter/` as a
complete worked example. Then run `/setup` in a project on that stack.
