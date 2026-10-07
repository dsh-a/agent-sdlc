---
name: sd-wire
description: Wire the agent-sdlc framework into a project via OMP's native extension points — skills.customDirectories, symlinked agents, and symlinked packs. Zero copy, single source of truth. TRIGGER when setting up agent-sdlc in a new repo, re-wiring after a framework refactor, or when the user asks how to connect their project to the SDLC pipeline.
---

# /sd-wire — wire agent-sdlc into a project

**This skill lives in the framework.** It used to live in a consuming project, which meant the
wiring recipe could not be reached by any *other* project and was lost whenever that repo reset a
branch. A deployment now reaches it the same way it reaches every other framework skill: via
`skills.customDirectories` *(omp)* or the `~/.claude/skills` symlink *(Claude Code)* — see § 5b.

Wire the agent-sdlc framework into any project so that `/cycle`, agent spawns, and
convention-aware skills all work — without copying a single framework file into the
project repo. The agent-sdlc repo remains the single source of truth; the project
carries only its own config and project-specific scaffold patterns.

## How it works

Three OMP-native mechanisms carry the framework:

| Piece | Mechanism | What it delivers |
|---|---|---|
| **Skills** | `skills.customDirectories` in `.omp/config.yml` | All 25+ skills: `cycle`, `project-conventions`, `test-rubric`, `minimalism`, etc. Discovered at startup alongside project-local skills. First-wins dedup on skill name. |
| **Agents** | Symlink `.omp/agents/` → agent-sdlc `.omp/agents/` | 13 omp-native task agent definitions: `scaffold`, `review`, `test`, `coding`, `ui-story`, `verify`, etc. |
| **Packs & patterns** | Symlink `.claude/packs/` → agent-sdlc `.claude/packs/` + scaffold pattern symlinks | Flutter conventions, test anti-patterns, scaffold templates (`interface.md`, `use-case.md`, etc.). Agents read these at runtime via `read` tool. |

Project-specific files that live in the project (not symlinked):

| File | Role |
|---|---|
| `.omp/config.yml` | Harness settings: `skills.customDirectories`, model roles, approval, isolation, retry |
| `.omp/agent-config.md` | Pipeline runtime config: project commands, architecture rules, branch config, context sources |
| `.claude/agents/scaffold/*.md` | Project-specific scaffold patterns (e.g. `syncable-entity.md`, `view-model-view.md`) |

## Prerequisites

- [omp](https://omp.sh) installed
- agent-sdlc repo cloned locally (default: `~/dev/agent-sdlc`)
- Project is a git repository

## Setup

### 1. Create `.omp/` skeleton

```bash
mkdir -p .omp
```

### 2. Create `.omp/config.yml`

```yaml
modelRoles:
  default: claude-sonnet-4-6    # adjust to your model
  smol:    claude-haiku-4-5-20251001
  slow:    claude-opus-4-7
  task:    claude-sonnet-4-6

# Point at agent-sdlc skills — zero copy.
skills:
  customDirectories:
    - /Users/<you>/dev/agent-sdlc/.claude/skills
  enableSkillCommands: true

tools:
  approvalMode: write
  approval:
    bash: allow

task:
  isolation:
    mode: auto
  mergeMode: branch
  maxConcurrency: 4
```

Adjust model IDs to match your OpenRouter or direct provider. See
agent-sdlc's `.omp/config.yml` for the full set of recommended settings.

### 3. Create `.omp/agent-config.md`

Copy from an existing wired project and customize:

- **Project Commands** — your test/lint/codegen commands
- **Architecture Review Rules** — layer boundaries, naming conventions
- **Branch Configuration** — `base_branch`, `feature_branch_pattern`
- **Docs Vault** — `vault_root` and `app_slug` (or leave empty)
- **Context Sources** — MCP servers to consult at pipeline stages

The `project-conventions` skill is already populated for Flutter; if using
a different stack, run `/setup` or copy from `packs/<lang>/conventions.md`.

### 4. Link the framework in

```bash
bash /path/to/agent-sdlc/deploy.sh link .
bash /path/to/agent-sdlc/deploy.sh grants          # paste into .claude/settings.json
bash /path/to/agent-sdlc/deploy.sh check .
```

That is the whole step. `link` creates every symlink a deployment needs — skills,
hooks, packs, `.omp/agents`, `.omp/hooks`, `RULES.md`, and each scaffold pattern
individually — and is idempotent, so re-run it after any framework update.
`check` changes nothing and exits non-zero if the deployment is wrong.

`grants` prints the Bash permissions the framework's scripts need, derived from the
framework's own `settings.json`. A missing grant does not fail the cycle — it stops it
to ask, which under a fan-out is a stalled clone nobody is watching. `check` reports
each one.

**This used to be two lists of files written out by hand here, and both drifted.**
The hook loop named `gate-log.py log-event.py` while the framework had three
hooks, so `guard-secrets.py` — the credential guard — was never deployed by
anyone following these instructions. The scaffold loop named 7 patterns out of
27, and one real deployment was found running the scaffold agent with 19 missing.
`deploy.sh` derives its manifest from what the framework actually contains, so
there is no list here to fall behind.

**Run `check` on a second machine before anything else.** A deployment is ~70
symlinks, each an absolute path into one checkout of the framework. Clone a
project somewhere else and they dangle — and a dangling hook fails *open*,
because the harness treats a hook error as non-fatal, so telemetry, gate capture
and the credential guard stop with nothing said. `check` distinguishes missing,
dangling, pointing-at-a-different-checkout, and shadowed-by-a-real-file, which
from inside a cycle all look the same.

**Do not commit the symlinks.** They encode one machine's paths. Add them to the
project's `.gitignore` and let `deploy.sh link` recreate them per machine.

A project's own scaffold pattern is kept: `check` reports a real file as an
override rather than a fault, and `link` refuses to clobber it. A real file where
a *hook* belongs is reported as a copy, because that is the measured stale-copy
bug — a project's copied `gate-log.py` fell a release behind and a whole fan-out
logged every row unclassified while looking healthy.

### 5b. Wire skills for Claude Code

Steps 1–5 wire **omp only**. `skills.customDirectories` is an omp mechanism; a Claude Code session
does not read it, and neither does a Claude Code subagent. Skip this step if the project only ever
runs under omp.

`deploy.sh link` already did both layers:

- **Project scope** — one symlink per framework skill into `.claude/skills/`, never a directory
  symlink, which would shadow the project's own skills. A project-local skill of the same name is
  never clobbered.
- **User scope** — `~/.claude/skills`, once per machine. **Not optional.** Untracked files are
  absent from a `git worktree` checkout, so a Phase-3 agent working inside
  `.claude/worktrees/agent-<id>` reaches framework skills through that absolute path alone. Without
  it, skills resolve in the project and not in the worktree, which reads as an agent ignoring its
  instructions. `deploy.sh` creates it when absent and reports — without touching — one that points
  somewhere else, since it is shared by every project on the machine.

Add the project-scope links to `.gitignore`, **outside** the agent-sdlc managed block so the block
regenerator does not rewrite them. They carry absolute machine-specific paths; committing them bakes
one machine's layout into the repo, and a clone elsewhere gets dangling links that fail silently.

Re-run `deploy.sh link` after any framework change. Nothing detects the drift on its own, which is
why `deploy.sh check` exists.

### 5c. Cycle clones need none of this

Measured 2026-09-06. A clone created with `omp worktree add` (with `worktree.clone = true`, the
default) inherits the **entire working tree**, including untracked and ignored files:

```
$ omp worktree add --detach --cwd <primary> <clones-root>/probe HEAD
Cloned from <primary> via apfs
```

Verified present and resolving in the clone: all 36 framework skill symlinks, `.claude/settings.json`,
both vault symlinks, `app_slug`, and `build/` + `.dart_tool/` — so the clone arrives wired *and*
warm, with no `pub get` and no re-wiring. On APFS the copy is copy-on-write: 1.8 G apparent (`du`)
for 4.1 MB actual (`df`).

Two consequences worth knowing:

- **`origin` is preserved** as the real GitHub URL, so `gh` works inside a clone. A plain
  `git clone --local` does not do this — its `origin` is a filesystem path and every `gh` call fails.
- **`agent_states/` is inherited too**, including any live `cycle-state-*.md` from the primary. A
  fresh clone must clear it, or the Phase-0 janitor will act on another cycle's state — offering to
  resume it, or deleting it.

### 6. Verify

```bash
bash /path/to/agent-sdlc/deploy.sh check .
```

Exits non-zero and names what is wrong. It distinguishes the cases that look identical from inside a
cycle — missing, dangling, pointing at a different framework checkout, and shadowed by a real file —
and reports a project-specific scaffold pattern as an override rather than a fault.

Then launch omp from the project root. The system prompt should list discovered skills from both
agent-sdlc (`cycle`, `project-conventions`, …) and project-local skills, and `/skill:cycle` should
load the orchestrator.

## How skills resolve

With `skills.customDirectories`, OMP's discovery pipeline looks like:

1. **native** provider (priority 100) — `.omp/` skills (none by default)
2. **claude** provider (priority 80) — `.claude/skills/` (project-local: `sb-*`, `agent-skills`, `sd-wire`)
3. **customDirectories** — merged after providers, first-wins on name collisions
4. **omp-managed** (priority 5) — auto-learn skills

Agent-sdlc skills appear alongside project-local skills. If a project defines a
skill with the same name as one from agent-sdlc, the project-local one wins
(higher precedence in the `claude` provider).

## When to re-wire

- After pulling agent-sdlc updates: just `git pull` in the agent-sdlc repo.
  Symlinks resolve to the updated files automatically.
- After adding a project-specific scaffold pattern: no action needed — it sits
  alongside the symlinked generic ones.
- After changing agent-sdlc's location: update `skills.customDirectories` in
  `.omp/config.yml` and re-create the symlinks.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Skills not discovered | Check `skills.customDirectories` path in `.omp/config.yml` points to agent-sdlc's `.claude/skills/`. The directory must contain `*/SKILL.md` subdirectories. |
| Agents not spawning | Verify `.omp/agents/` symlink resolves. Check agent `.md` files have `name` + `description` frontmatter. |
| Scaffold agent can't find patterns | Verify `.claude/agents/scaffold/` has the symlinked pattern files. The agent reads them at runtime. |
| `project-conventions` feels wrong | The skill is pre-populated for Flutter. For other stacks, run `/setup` or manually edit agent-sdlc's `.claude/skills/project-conventions/SKILL.md`. |
| Model not found | Check `modelRoles` in `.omp/config.yml` match your `~/.omp/agent/models.yml`. |
| Symlink broken after moving agent-sdlc | Re-run steps 4–5 with the new path. Symlinks are absolute. |