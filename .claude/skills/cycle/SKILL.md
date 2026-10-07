---
name: cycle
description: SDLC feature pipeline orchestrator. Run /cycle to go from a feature description to a tested, reviewed PR — creates PRD, generates tasks, spawns parallel implementation agents, verifies, reviews, and opens the PR. Supports --mode full|lean|hotfix, --exe, --manual, and resume from state file.
disable-model-invocation: true
---

# Cycle — SDLC Feature Pipeline

You are the orchestrator. You run at the opus tier (under omp, `modelRoles.slow`; under Claude Code a session's model is fixed when it starts, so the allocation table's `orchestrator` row is intent, not a setting — verify it yourself if it matters). Manage gates, delegate to agents, make judgment calls. You do not write implementation code — spawn agents for that.

Feature or PRD: **$ARGUMENTS**

**One cycle per session.** If a `/cycle` already ran in this session, stop and tell the user to `/clear` (or open a new terminal) before starting another. Invoking `/cycle` twice leaves **two copies of this skill resident** — measured at 43,598 tokens each — and it is what puts sessions over the context window: sessions with one invocation peak at a median 235,217 and exceed 262,144 in 8 of 27; with two, 278,415 and 17 of 26. You already hold this skill; do not read `SKILL.md` back.

## Configuration

`.omp/agent-config.md` holds model allocation, effort settings, artifact paths, optional agents and cycle options. **Query it, do not read it** — it is 360 lines of tables and you need single cells:

```sh
python3 .claude/skills/cycle/config-get.py base_branch
python3 .claude/skills/cycle/config-get.py model verify        # via the active preset
python3 .claude/skills/cycle/config-get.py --keys vault_root app_slug
```

Exit 0 found, 1 not found (`--default X` supplies one), 2 **ambiguous** — a name in two sections, so pass `--section`; never guess which table won. 3 means no config: fall back to sonnet for implementation agents, haiku for pre-digest and monitor, opus for orchestrator. Reading spans of this file cost v0 run 2 ~4,600 tokens and still left the model resolving a spawn by hand.

When passing `model:` to a spawn, take the label from **Model Allocation** — then resolve it **per harness**:

- **Claude Code** — pass the label verbatim (`opus` / `sonnet` / `haiku`; `fable` also exists). The `Agent` tool's `model` parameter is a fixed tier enum and **rejects a concrete model id**. Do not consult Model Versions; its ids are omp's naming and mean nothing here.
- **omp** — resolve through **Model Versions** and pass the concrete id (e.g. `claude-opus-4-6`). If no Model Versions table exists, pass the label as-is.

Getting this backwards fails the spawn outright under Claude Code, and it is the kind of instruction that reads as harness-neutral when it is not.

## Live Environment (auto-injected)

Active cycle states:
!`ls agent_states/cycle-state-*.md 2>/dev/null || echo "none"`

**Deployment check** — your **first action**, before reading anything else and before Phase 1:

```
bash .claude/skills/cycle/preflight-deploy.sh
```

It ends in a `PREFLIGHT:` line. `ok` — continue. `problems` — **stop and fix it before Phase 1**,
with the command it prints, then re-run. `unreachable` — see below.

This is a refusal rather than a warning because the failures it catches are invisible from inside a
cycle. A hook whose path no longer resolves fails *open* — the harness treats a hook error as
non-fatal — so telemetry, gate capture and the credential guard stop with nothing said, and the run
report comes back saying gate wait was "not captured" as though nobody had waited. Measured: one
deployment was missing 19 of 27 scaffold patterns, and the `scaffold` agent had been running without
them for as long as they had existed.

Two results are **not** failures and do not block: `override` (a real file where a scaffold pattern
belongs — a project-specific pattern, which is allowed) and a `USER … different framework` note
(`~/.claude/skills` is shared by every project on the machine, so it is reported and never
re-pointed). A `COPY` line *is* a failure: a copied hook goes stale invisibly, which is the bug that
made a whole fan-out log every row unclassified while looking healthy.

If the shim reports `unreachable`, say so in the run report's Harness findings rather than proceeding
silently — an unverifiable deployment is a different claim from a verified one. The same applies if
the harness refuses to run it at all.

This is a body step and not a `!`...`` substitution on purpose. In fan-out 6 the auto-mode classifier
refused to expand the substituted form in **one session out of five** — same string, same settings,
same minute, reason `[Code from External]` — and a denied `!`...`` aborts the *entire* slash command,
so that cycle received no skill body and sat idle until a human noticed. A refused body step is a
finding you can report; a refused expansion is a run that never starts.

**Call every scoped script by its project-relative path**, never an absolute one, here and
everywhere below. Grants are string matches: `python3 .claude/skills/cycle/clear-agent-states.py`
matches, and `python3 /Users/you/dev/cycles/c5/.claude/skills/cycle/clear-agent-states.py` matches
nothing and falls through to the classifier, which refused exactly that at Finalize in fan-out 6
(`[Irreversible Local Destruction]`). Every one of these scripts runs from the project root, so the
relative form always resolves.

**Janitor check**: for each state file listed above, check whether a matching cycle report already exists in `cycle_reports/` (match by feature name substring). If a match exists, the cycle completed without sending `FINALIZE` — delete the state file now and do not offer to resume it.

**Task-branch janitor**: isolated tasks leave branches and, under Claude Code, worktree
directories. Prune whatever belongs to a cycle that is **not** among the active state files
above (orphaned from a crashed or interrupted cycle):

| Harness | Artifact | Prune |
|---|---|---|
| omp | `omp/task/<id>` branches | `git branch -D <branch>` |
| Claude Code | `worktree-agent-<id>` branches | `git branch -D <branch>` |
| Claude Code | `.claude/worktrees/agent-<id>` directories | `git worktree remove <path>` (add `--force` only if it is dirty and its cycle is orphaned) |

```sh
git branch --list 'omp/task/*' 'worktree-agent-*'
git worktree list --porcelain
```

omp cleans up its own isolation workspaces on completion; Claude Code does not clean up either
artifact, so this janitor is the only thing that does. Never prune a branch or worktree whose
cycle is still active.

**Gitignore guard** — ensure runtime artifacts are never committed to the project repo.

The guard **regenerates** the managed block rather than appending it. The previous version
grepped for `agent-sdlc (managed)` but wrote `agent-sdlc (managed — do not edit)`; the literal
never matched, so it appended on every run and the block accumulated. Strip-then-write is
idempotent by construction and also repairs repos that already collected duplicates:

!`bash .claude/skills/cycle/sync-gitignore.sh 2>&1 || true`

It reads `vault_root` out of `.omp/agent-config.md` **in the same pass** and emits the three
vault paths when it is set. It has to: this runs at prompt expansion, before the model has read
anything, so a base block written now and corrected by the vault guard later leaves the working
tree wrong in between — and wrong for good if the cycle short-circuits before the guard runs.

**It never strips on uncertainty**, and this is the part that took two incidents to get right.
The script edits a *tracked* file, and removing the vault lines turns `cycle_reports`,
`agent_tasks/reports` and `agent_tasks/prds` into untracked symlinks: the tree goes dirty, and
committing that pulls vault-class artifacts back into the app repo — precisely what the vault
exists to prevent. The inlined version could not tell *"no vault configured"* from *"could not
read the config"* and stripped for both. It did that twice in a deployment whose `vault_root`
was set the whole time. So now an unreadable config **keeps whatever vault lines are already
present** and says so on stderr; only a config that was read, and genuinely has no `vault_root`,
removes them.

Paths resolve from the git root rather than the working directory, so a cycle started from a
subdirectory cannot read no config, conclude no vault, and strip.

`--check` reports drift without writing. `tests/test_sync_gitignore.sh` pins the behaviour,
including that reverting to strip-on-unknown fails the suite.

Call this recipe the **block regenerator**. The vault guard below re-runs it; because it strips
first and derives the same content from the same config, the re-run is now a no-op confirmation
rather than a repair.

What is ignored, and why:

| Path | Class | Rationale |
|---|---|---|
| `agent_states/` | runtime | cycle state + telemetry; per-machine |
| `agent_tasks/tasks-*.md` | runtime | see below |

`documentation/` is **durable** — it travels with the feature branch and must stay committed.

**PRDs are vault-class.** `agent_tasks/prds/` is a symlink into the docs vault (wired by the
Vault link guard below), so PRDs never land in the project repo — same as cycle reports and run
reports. With no `vault_root` configured it is an ordinary directory and PRDs are committed
locally, which is the backward-compatible default.

**Task files are runtime, not durable.** The checkbox state in `tasks-*.md` is working
state, not a deliverable, and committing it puts pipeline scaffolding in every PR. Isolated
agents therefore cannot tick their own boxes: the orchestrator owns the task file and ticks
it centrally as agents report completion. Say so in the spawn prompt — an agent that expects
to tick its own list and finds the file absent will otherwise burn calls working around it,
or copy the file into its worktree. **Sub-task state is the orchestrator's record of what
agents reported, not a shared scratchpad.**

**Vault link guard** — read the **Docs Vault** section of `.omp/agent-config.md`. If `vault_root` is non-empty, wire the vault before any report is written this cycle:
1. Resolve `app_slug` (config value, else the basename of the repo root).
2. Ensure the vault targets exist:
   ```sh
   mkdir -p "{vault_root}/cycle_reports/{app_slug}" "{vault_root}/reports/{app_slug}" "{vault_root}/prds/{app_slug}" "{vault_root}/product/{app_slug}"
   ```
3. Wire each of these four pairs:

   | Repo path | Vault target |
   |---|---|
   | `cycle_reports` | `{vault_root}/cycle_reports/{app_slug}` |
   | `agent_tasks/reports` | `{vault_root}/reports/{app_slug}` |
   | `agent_tasks/prds` | `{vault_root}/prds/{app_slug}` |
   | `product` | `{vault_root}/product/{app_slug}` |

   `product` is hand-owned input the pipeline only reads — customer profiles for `/refine` — so
   it is linked but gets **no** `Edit` grant from `deploy.sh grants`.

   For each: if the repo path is already the correct symlink, skip; if it is a real directory,
   move its contents into the vault target then `rm -rf` it; finally `ln -s` the vault target to
   the repo path. Moving before linking is what makes this safe to run on a repo that already
   has local PRDs — they migrate into the vault rather than being orphaned.

4. **Hand over the grant this creates.** Every report write now leaves the repo, so each one
   prompts — ~14 minutes of one cycle's 35-minute permission total, recurring every cycle.
   `bash <framework>/deploy.sh grants <project>` emits the `Edit(...)`/`Read(...)` lines; paste
   them into the project's `.claude/settings.json` `allow`, and the directory line it prints
   under its own heading into `permissions.additionalDirectories`.

   **Both halves are load-bearing, and the spelling is not cosmetic.** Claude Code consults path
   rules for `Edit` and `Read` only — a `Write(...)` path rule is accepted, never matched, and
   warned about at startup — and an absolute path needs a `//` prefix, because a single leading
   `/` anchors at the settings source rather than the filesystem root. Without the
   `additionalDirectories` entry the allow rules do nothing either: a path outside the working
   set is refused before any allow rule is read. This grant was spelled `Write(/abs/path/**)`
   until 2026-10-05 and was inert on both counts, so the 14 minutes it was written to reclaim
   were still being paid.

4. Re-run the **block regenerator**. With `vault_root` set it emits `agent_states/`,
   `agent_tasks/tasks-*.md`, `cycle_reports`, `agent_tasks/reports`, `agent_tasks/prds` (no
   trailing slash — git treats a symlink as a file, so `dir/` would not match). The injected
   pass at startup already wrote exactly this, so the re-run should be a no-op; it exists to
   cover the case where you created the vault symlinks during *this* cycle and the startup pass
   ran before `vault_root` was set.

   **Then check `git diff .gitignore` and stop if it is non-empty.** A diff here means the two
   passes disagreed, which is the failure this ordering was designed to remove — report it
   rather than committing whichever version happens to be on disk.

   **Consuming repos: keep vault rules inside the managed block.** A hand-written ignore rule
   for a vault path placed outside it will drift the moment these paths change — and one placed
   inside a *different* block is erased on the next run.

If `vault_root` is empty, skip entirely — reports and PRDs stay local and committed (backward-compatible default).

Recent cycle reports:
!`ls cycle_reports/*.md 2>/dev/null | tail -5 || echo "none"`

Current branch:
!`git branch --show-current`

---

## Execution mode

Dry-run by default. Completes Phases 1–2 and Phase 3 dependency analysis, then presents a plan (agent assignments, models, parallelism) without spawning implementation agents.

**Under omp**, the dry-run maps to omp's native plan mode. Launch the session with `--plan`:
```bash
omp --plan
/cycle Add CSV export to the reports page
```
omp plan mode restricts tools to `read`/`search`/`find`/`lsp`/`web_search` — no writes, no task spawns — preventing accidental implementation during dry-run. This is the equivalent of running `/cycle` without `--exe`, but enforced at the harness level. When `--plan` is active, skip the `--exe` flag entirely (plan mode cannot spawn agents).
Also accepts PRD paths, task file paths, or state files (for resume). Resuming from a state file implies `--exe`.

Pass `--manual` to use manual mode: `/cycle --manual agent_tasks/tasks-prd-feature.md`

`--manual` delegates to `/process-tasks` logic — one sub-task at a time with user approval gates after each. No parallel agents, no worktrees. Still creates a state file for resume capability. Requires a task file path (or will prompt for one).

### `--parallel` — fan out across issues

```
/cycle --parallel 419 404 378
/cycle --parallel 408 435 383          # each issue runs at its own refined Depth
```

**You are a launcher here, not an orchestrator.** Run the setup script, report what it printed, and
stop. Do not create a PRD, do not spawn agents, do not manage the resulting cycles — each clone
gets its own orchestrator session, and one session steering several features is the
god-orchestrator the framework rejects (`docs/internal/parallel-cycles-plan.md` §0).

**Do not pass `--mode` unless the user asked for it.** Each issue carries its own `Depth`
(5.6.7), so the bundle can mix `full` and `lean` and every clone gets the depth its story was
refined to. A `--mode` on the launcher overrides all of them at once, which is what you want for
a deliberately uniform measured run and nothing else. Pass nothing else unless asked:

```sh
bash .claude/skills/cycle/start-parallel-cycles.sh [--mode lean] [--dry-run] [--no-launch] <issue> <issue> ...
```

**A repeat run needs no extra flags.** The script reaps the previous run's clones and
fast-forwards the base itself, because it would otherwise just refuse over both. Neither step
improvises: reaping checks every clone before removing any and refuses on uncommitted work or an
attached session, and the sync refuses a dirty tree and takes only a fast-forward. Reaping archives
the previous run's gate log and provenance under a timestamp, so two runs never share one log.
`--no-reap` / `--no-sync` opt out.

**Between runs, sweep instead of waiting for the next launch.** Each cycle's Finalize now deletes its
clone's build output and marks the clone reapable, so what is left behind is a ~30M husk rather than a
1.8G one. To remove the husks:

```sh
bash .claude/skills/cycle/reap-clones.sh sweep --root <clones-root>          # list
bash .claude/skills/cycle/reap-clones.sh sweep --root <clones-root> --apply  # remove
```

`sweep` removes only clones a cycle explicitly marked finished, whose HEAD has not moved since, which
are clean and have no process attached. It is not merge-aware by design: whether a PR merged is a fact
about the PR, not the clone — branches can stay open a long time or forever, and the branch survives
removal regardless, since a clone is a linked worktree whose branch lives in the origin's `.git`.

This does **not** replace the launcher's reap above, which removes *every* clone under the root. A
cycle that crashed before Finalize leaves an unmarked clone that `sweep` will not touch and the next
launch must.

`--mode` is forwarded to every cycle and **overrides every story's `Depth`** — which is why the
launcher refuses it alongside more than one issue for `hotfix`: that mode skips Gate 1, Gate 2 and
review and forces verify to lite, which also skips verify's
falsification re-run — a fan-out in hotfix mode exercises almost none of the machinery a fan-out is
usually run to observe. Cycles open as tabs where the terminal supports it; `--windows` forces
separate windows.

The script preflights the tree, creates one detached clone per issue via `omp worktree add`, clears
each clone's inherited `agent_states/`, claims the issues, records the framework SHA and disk
baseline, and opens a terminal per clone.

**It refuses rather than degrades.** A failed precondition exits
non-zero and does nothing: a clone copies the working tree, so a dirty or wrongly-branched primary
does not merely inconvenience the run, it contaminates every cycle in it. Report the refusal
verbatim and stop — do not work around it, and do not re-run with flags that skip the check.

One thing to pass on to the user, because nothing enforces it:

- **There is no per-cycle agent cap under Claude Code** (`maxConcurrency` is omp-only), and the
  script does not instruct one. That is deliberate: what a fan-out reaches uncapped is the
  measurement (plan §18.1, Q-D1). `--max-agents N` prints a cap to pass on, and says that doing so
  makes the run a capped trial rather than the uncapped baseline.

Gate raise and answer times need no discipline — the `gate-log.py` hook records every one, and the
script says at preflight whether capture is active. Read them with `gate-report.py`.

Fan-out is experimental. Read `docs/internal/parallel-cycles-plan.md` and its runbook before the
first one.

### Cycle modes (5.6.1, 5.6.3)

`/cycle --mode full|lean|hotfix` selects the depth of the pipeline. Default is `full`. Modes are **never picked silently by the orchestrator** — the depth is either declared on the story (board field `Depth`, see below), passed as `--mode`, or asked about at dry-run.

**Behavior matrix:**

| Phase | `full` | `lean` | `hotfix` |
|---|---|---|---|
| 1A PRD | yes | inline — derive AC from the feature description; skip `create-prd` spawn | skip |
| 1C gate | yes | **merged with 2B** (one combined approval) | skip |
| 2 task gen | yes | yes | skip (single implicit task) |
| 2B gate | yes | **merged with 1C** | skip |
| 3 implementation | parallel agents in worktrees | parallel agents in worktrees | single agent, **no worktree** (main checkout) |
| 4A wrap-up | verify + review concurrently | verify + review concurrently | lite verify only; no review |
| 4B release | yes | yes | yes |

**Gate consolidation in lean.** When `--mode lean`, Phases 1C and 2B fuse into one approval point at the end of Phase 2: the user reviews the inline-derived AC summary *and* the generated task list together, then approves once. PRD is not written to a file; the AC summary lives inside the cycle state's `## References` section.

**Hotfix posture.** `--mode hotfix` is for "fix one thing, fast." Single implicit task derived from the feature description (no `generate-tasks` spawn). Implementation runs on the feature branch directly — no worktree, no parallel agents, no pre-digest. Verify runs at **lite** depth (see 5.6.6). Review is skipped. The feature branch and PR open as normal in 4B.

**Mode is recorded** in cycle state's `## References` section as `Mode: full|lean|hotfix` for the run report and `self-improve` aggregation.

### Depth is a property of the story (5.6.7)

`--mode` is a *launch-time* flag, so it can only ever hold one value. Blast radius is a fact
about the issue. When several issues are started together — a fan-out, or a continuous loop
pulling the next refined story — one flag cannot be right for all of them.

So the depth lives on the story, in the board's **`Depth`** single-select field
(`full` / `lean` / `hotfix`), written by `/refine` at Step 8 alongside the READY verdict. That
is the one moment someone has read the body, run codebase grounding, and knows whether the work
touches a schema. `Refined` therefore implies `Depth` is set — it is part of the Definition of
Ready.

**Precedence, highest first:**

1. An explicit `--mode` on the invocation. The operator's declaration always wins.
2. The issue's `Depth` board field, when the argument is a tracker reference.
3. The dry-run heuristics below (5.6.4), for descriptive prose.
4. Ask.

Read it once, at Step 1, with the project resolved from `.omp/agent-config.md` § Artifact Paths
(`Roadmap | project:<owner>/<number>`):

```sh
gh project item-list <number> --owner <owner> --format json \
  | jq -r --argjson n <issue> '.items[] | select(.content.number==$n) | .depth // ""'
```

A board with **no `Depth` field at all** is not an error — an older deployment simply has not
added it. Fall through to rule 3. A board that *has* the field with an **empty value** for this
issue is a gap in refinement: say so, and ask.

Record which rule fired in cycle state's `## References` as
`Mode source: flag|story|heuristic|asked` next to `Mode:`, so `self-improve` can tell a
depth someone chose from a depth nobody did.

**`hotfix` is sequential-only.** Never run it in a fan-out bundle: it skips Gate 1, Gate 2 and
review and forces verify to lite, so the clone exercises almost none of the machinery a fan-out
is run to observe. A bundle is `full` and `lean`, mixed freely.

### Mode auto-suggestion at dry-run (5.6.4)

If the user did **not** pass `--mode` **and the story carries no `Depth`** (5.6.7), apply these
heuristics on the feature description and surface a suggestion at dry-run. **Never pick
silently** — the user always confirms or overrides.

**Suggest nothing** when the argument is a bare tracker reference — an issue number (`#412`,
`412`), a legacy `BUG-NNN` token, or a URL, with no descriptive prose. Read the issue's `Depth`
field; if it is unset, ask for the mode instead.

A tracker ID carries **no blast-radius signal**: `/cycle BUG-088` matched every `hotfix`
condition below, but the work changed a ViewModel's lifetime across every entry path into a
screen and touched two layers. The heuristics read the argument string; the argument string
described nothing. This is the defect `Depth` exists to remove — refinement reads the *body*,
with grounding, and records what it found.

**Suggest `hotfix`** when ALL of:
- The argument is descriptive prose (not a bare tracker reference — see above).
- Description contains any of: `fix`, `bug`, `hotfix`, `patch`, `regression`, or matches `^fix:` style.
- Description is ≤ 20 words.
- Description contains NONE of: `migration`, `schema`, `refactor`, `redesign`, `new feature`, `epic`.

**Suggest `lean`** when ALL of (and hotfix-eligibility is false):
- Description is ≤ 40 words.
- Description contains NONE of: `migration`, `schema`, `multi-screen`, `epic`, `refactor`.

**Else suggest `full`.**

At dry-run, print exactly:
```
Suggested mode: <suggestion>. Reason: <short trace of the heuristic that fired>.
Override with --mode full|lean|hotfix.
```

If the user passed `--mode` explicitly, **suppress the suggestion entirely** — their declaration wins. Record the suggestion-vs-actual outcome in cycle state's `## References` as `Mode suggestion: <suggested> | accepted: true|false` so `self-improve` can later calibrate the heuristics from observed acceptance rates.

Dry-run ends with: **"Ready to execute? `/cycle --exe` to begin, or adjust first."**

---

## Agent spawn rules

### Phase-3 isolation

Isolation works differently under each harness. **Read the subsection for the harness you are
running in** — assuming the omp path under Claude Code is what put three of four agents ~90
commits behind their base.

#### Under omp

Each Phase-3 implementation agent spawns with `isolated: true`. omp captures a baseline from
the current HEAD (the feature branch), creates an isolated workspace, runs the agent, commits
to a task branch (`omp/task/<id>`), and cherry-picks into the parent (feature branch). omp
owns provisioning and merge — no manual `git worktree add`, no manual merge/teardown.

**A task whose input is untracked cannot be isolated, at any base.** `git worktree add`
materialises tracked content only, so a working-tree file — a dataset a human dropped in,
anything gitignored — is absent from every workspace. No base check catches it: the agent sees a
missing file and reports the wrong cause. Check the task's inputs first:

```sh
git ls-files --error-unmatch <input-path> >/dev/null 2>&1 || echo "untracked — run non-isolated"
```

#### Under Claude Code — **do not request worktree isolation**

`isolation: "worktree"` provisions from **`main`**, never the session's branch, and no parameter
changes it. Measured directly: a session on a feature branch at `11e0ef0` got an agent worktree
at `3fc58b2` — `main`. In myapp that was 540 commits behind. (myapp's nominal default is
`master`, so "it uses the default branch" does not explain it; the reliable invariant is just
*never the session branch*.)

So spawn Phase-3 agents with **no isolation** — they share the main checkout on the feature
branch, the only base you control. Two agents on one branch race, so tasks in a wave run
**sequentially**. That trade is correct: a sequential cycle on the right base beats a parallel one
diffing against code deleted 540 commits ago. For real parallelism, use the fan-out clone model
(§ Inside a fan-out clone) — each clone is a full checkout at a base you chose.

If you request isolation anyway, the base check below is all that stands between you and a diff
against deleted code.

1. Resolve and record the base before spawning:
   ```sh
   git rev-parse --short HEAD    # on the feature branch — this is the base for every spawn
   ```
   Put the resulting SHA in cycle state and in every spawn prompt. **Recording it does not pin
   anything** — it is what the agent checks against, nothing more.

2. **Every agent's first action is a base check.** Include this verbatim in the
   spawn prompt — it is a safeguard, not a nicety:

   > Before anything else, run `git log --oneline -3`. Your base must be `<sha>`
   > (`<subject>`). If it is not, or the working tree is dirty, **stop and report
   > `WORKTREE MISMATCH: expected <sha>, got <actual>`** — do not `git reset`, do not
   > continue, do not work around it. If the code you find contradicts your briefing digest,
   > that is the same signal: stop and report.

3. On a `WORKTREE MISMATCH` report, do not have the agent self-repair. **Respawn without
   isolation** — re-requesting it reproduces the same base — and emit
   `RESCUE worktree-base [agent-id]` to monitor so the run report carries it.

The mismatch rescue exists because an agent that trusts its environment writes a diff against
deleted code — and that diff does not merge. An agent that "fixes" it with `git reset --hard`
is silently discarding whatever else was wrong.

#### Inside a fan-out clone — no nested isolation

Check this before Phase 3, in any harness:

```sh
test -f agent_states/.fanout-clone && echo "fan-out clone — isolation off"
```

When the marker is present the checkout is a clone created by
`start-parallel-cycles.sh` for a parallel run. **Do not isolate Phase-3 agents.**
Spawn them in the clone directly (`isolated: false`, no `isolation: "worktree"`),
on the feature branch, one task at a time where they touch the same files.

The clone *is* the isolation the parallel design provides; a second nested layer
buys nothing and breaks two things at once. Measured in fan-out 1
(`docs/internal/parallel-cycles-evidence-run1.md` E2): Claude Code provisioned the
workspace at `origin/main` — 244 commits behind the session's actual base — and
placed it under the **primary repo**, not the clone the session was running in. A
colliding branch is noisy; a wrong base is silently wrong, and a workspace outside
the clone defeats clone-per-cycle isolation entirely.

**A refused command is answered once, not retried.** If a tool call is denied — by a permission
rule, by the auto-mode classifier, or by a human — do not reissue it, reword it, or try the same
thing through another shell. Record what you could not do and why, in cycle state and in the run
report's Harness findings, then work around it or stop. Measured in fan-out 8: one orchestrator
reissued a single denied command **101 times**, which is every denial that round bar one. It
produced no new information after the first, and the gate log now captures refusals, so a retry
loop is recorded 101 times as well.

If the refusal is blocking real work, escalate to the operator with the command, the reason, and
what it stops you doing. That is one question, not a hundred attempts.

**Never prefix a command with `cd <clone>`.** Your working directory is already the
clone; the `cd` buys nothing and costs a permission dialog on every command that
carries it. A permission grant is a prefix match against the whole command string,
so `cd /path/to/clone` ⏎ `git push -u origin HEAD` matches the grant
`Bash(git push -u origin HEAD)` **not at all** — it is a different, longer command.
The same is true of `&&` chains and `;` sequences: granted words joined together
are an ungranted command.

Measured in fan-out 4: **18.5h of permission-dialog wait across 6 asks**, against
1.6h of real gate wait, every one of them a command the project had already
granted and the `cd` had un-granted — 8h03m on a `CHANGELOG.md` edit, 7h13m on
`git add` + `git commit`, 2h57m on `git push`. Three clones each spent most of a
night parked on a dialog for work they were allowed to do. Issue one command per
call, unprefixed, and let the harness match it.

**Mode override:** in `--mode hotfix`, isolation is skipped. A single implementation agent runs in the main checkout on the feature branch (`isolated: false`). The rest of this section applies only when mode is `full` or `lean`.

**One isolated workspace per agent** (both harnesses) — the implementer and test agent no longer share a worktree. The implementer commits → the task branch merges into the feature branch → the test agent gets a fresh workspace from the updated HEAD. This is cleaner: the test agent sees committed, merged code rather than worktree-local state.

**Dependency ordering:** dependent tasks fork from the post-merge HEAD — spawn a dependent task only after its prerequisite's isolated agent has completed and its branch is merged. Under Claude Code, re-resolve the base SHA after each merge; the pinned base for a dependent task is the *new* HEAD, not the one recorded at Phase-3 start.

**Handoff format** — every Phase-3 implementation agent's final response must include a `## Deviations` section. Each item: `task: [task-id] | ac: [AC ref] | implemented: [what] | reason: [why]`. Write `None` if the implementation matches PRD AC literally. The orchestrator forwards each deviation to monitor via a `DEVIATIONS` message (see §3.4 Success).

Named agents (`scaffold`, `ui-story`, `test`, `pre-digest`, etc.) have their model set in their definition. Pass `model:` only to override. There are no unnamed agents left to spawn generically — `pre-digest` was the last one, and spawning it as a stand-in cost fan-out 6 two hand-transcribed digests.

### Agent identity (`role` field)

Every task spawn includes a `role:` field — a short identity string that becomes the agent's system-prompt persona and registry display name (visible in `irc(op: "list")`). Format: `<role> (task <task-number>)`. Example: `role: "Scaffold engineer (task 2.0)"`. This replaces the old `label` frontmatter convention for status display.

### Shared context (`local://` files — on-demand, not injected)

Write each piece of shared background to a `local://` file once. Subagents share the parent's `local://` root. Each agent's `assignment` references only the files it needs — the agent reads them on demand via the `read` tool. This avoids injecting the full shared context as input tokens into every agent's system prompt (which the `context` field would do).

**Granular files** (write once, reference per-agent):

| File | Contents | Who reads it |
|---|---|---|
| `local://prd.md` | PRD path + feature description | implementer, test, verify, review |
| `local://ac.md` | Pre-extracted AC from PRD | test, verify, implementer |
| `local://ctx-sources.md` | Context-source blocks (stage `implement`) | implementer, test |
| `local://digest-<task>.md` | Pre-digest summary for task N | implementer for task N only |
| `local://commands.md` | Project Commands (test, analyze, codegen) | any agent that runs them |

**Do NOT use the `context` field** for batch spawns — it raw-injects all shared background into every subagent's system prompt as input tokens. Use `local://` files + `read` instead so each agent pulls only what it needs. Pass an empty `context` (or minimal one-liner) in batch calls; the `assignment` carries the `local://` file references.

**Prompt budget**: pre-digest prompts <200 words. Implementation agent `assignment`: sub-task list + `local://` file references only — instructions live in the agent definition.

### Context Sources retrieval

A reusable step invoked at five stages (`prd`, `tasks`, `implement`, `review`, `verify`). The full contract is in the `context-sources` skill; the mechanics:

1. Read `.omp/agent-config.md` § Context Sources. Select rows where `enabled` is `true` **and** `consult_at` contains the current stage. If none, skip silently.
2. For each selected `mcp` source: query it once with the row's `query_hint` plus concrete context (feature name, the task's Relevant Files, touched symbols). For `skill` sources, run the named skill.
3. Write the trimmed result to `local://ctx-sources.md` (append per source). Each agent's `assignment` references this file if it needs context-source data. Instruct the agent to echo `context-sources-consulted: <ids|none>` in its handoff.

This is the same inject-downward pattern as Pre-digestion and Known pitfalls. `predigest` is intentionally **not** a consult stage by default (the pre-digest is a cheap summarizer).

### Handoff validation

At every agent handoff, the orchestrator confirms the agent's frontmatter `produces:` file exists at the expected path. Missing = agent failure: re-spawn (Phase 1A / 2), escalate (Phase 3), or run **Stall salvage** (Phase 4A — already wired).

---

## Branch strategy

All work on feature branches, never directly on the base branch.

- **Naming**: read `feature_branch_pattern` from the **Branch Configuration** table in `.omp/agent-config.md`. Default: `feature/[short-description]`, `fix/...`, or `refactor/...`
- **Create at Phase 2B**: `git checkout -b feature/[name] [base_branch]` — where `[base_branch]` is the `base_branch` value from `.omp/agent-config.md`
- **Parallel tasks**: each isolated agent gets its own workspace from `feature/[name]` HEAD. omp creates `omp/task/<id>` branches and cherry-picks into `feature/[name]` on completion. See **Phase-3 isolation** (§ Agent spawn rules).
- **Merge order**: dependency order. Run the test and typecheck/lint commands (from **Project Commands** in `.omp/agent-config.md`) after each merge.
- **Conflicts**: sonnet agent resolves. Ambiguous conflicts → escalate to user.
- **After Phase 4**: do NOT merge into the base branch. User decides after `/verify` + `/review`.

---

## State persistence

State directory: `agent_states/` (ephemeral — deleted on completion).

### State persistence

The orchestrator keeps `agent_states/cycle-state-<feature>.md` current throughout the cycle, using the template and verb list in `.omp/agents/monitor.md`.

**Edit that file with the `Edit` tool, never with `sed`.** It is a Markdown document full of pipe
tables, backticks, brackets and `#123` issue references — every one of which is a metacharacter to
some layer of shell quoting. `Edit` matches an exact string and fails loudly when the match is not
unique; `sed -i` silently does nothing, or the wrong thing, and returns 0 either way.

Measured in fan-out 7, one cycle, three failures: a `#` delimiter collided with `#462` in the row
text; a `[` inside a double-quoted `sed` broke the expression and wrote `test_files_touched:false`
into state; and zsh's `$ref:t` modifier mangled a `git show` path so the counts came back 0. Each
was caught by reading the command's output and redone. **None changed a decision, and the second
wrote a wrong value that would have fed `self-improve`** — which reads this file and cannot tell a
measured `false` from a quoting accident. **Two modes**, selected by `agent_messaging` in `.omp/agent-config.md` § Cycle Options (default `false`):

- **`agent_messaging: false` (default) — inline.** *You*, the orchestrator, write the state file directly. The monitor's verb list (`GATE`, `SPAWNED`, `PARENT`, `RESCUE`, `DEVIATIONS`, `SCOPE_CHANGE`, `SUPERVISOR_HEALTH`, …) is your **checklist of what to record when**. This is the normal path and is **not** a degradation — never log it as a rescue. No background monitor is spawned. Inline is also the only mode that works without the irc tool / agent-teams.
- **`agent_messaging: true` — delegated.** Spawn the background monitor once at Phase 3 start. The monitor blocks on `irc(op: "wait", from: "Main", timeoutMs: 0)` to receive verbs in real time — send each verb via `irc(op: "send", to: "<monitor-id>", message: "<verb>")`. It writes the state file so your context stays lean:
  ```
  Spawn the `monitor` agent (model tier: haiku, id: "monitor") as a background task with this prompt:
  > Feature: [name]. State file: agent_states/cycle-state-[name].md. You are in streaming mode — block on irc(op: "wait", from: "Main", timeoutMs: 0) to receive state-update verbs. Write each verb to the state file immediately. On FINALIZE, archive and clean up.
  ```

**Reading convention for the rest of this skill:** wherever a step says "emit / send / forward / update `<VERB>` to monitor," it means *record that verb in cycle state* — write it inline (default) or send it to the monitor via the `irc` tool (when `agent_messaging: true`). Verb formats are defined in `monitor.md`.

**Save-before-spawn:** before spawning any sonnet/opus agent, bring the state file current first (inline) or send the pending verbs to the monitor — so a crash mid-spawn leaves an accurate recovery point.

**Finalize is always a one-shot spawn.** Regardless of mode, cleanup runs as a single short-lived monitor spawn — it holds the `python3 .claude/skills/cycle/clear-agent-states.py` permission the orchestrator does not:
```
Spawn the `monitor` agent (model tier: haiku) with this prompt:
> FINALIZE report:[run-report-path]. Archive per monitor.md, delete all agent_states/ files for this cycle, then exit.
```

---

## Entry point

Inspect $ARGUMENTS:

| Input | Start at |
|---|---|
| State file (`agent_states/cycle-state-*.md`) | Resume: read state + digests, verify codebase, resume state persistence (§ State persistence), skip completed phases |
| PRD file (`agent_tasks/prds/prd-*.md`) | Phase 1B |
| Task file (`agent_tasks/tasks-*.md`) | Phase 2 review |
| Story number (e.g., `1.6`) | Phase 1A (pre-populate from the story issue: `gh issue list --label story --search "1.6 in:title"`) |
| Feature description (text) | Phase 1A (check the story issues for a match first: `gh issue list --label story --search "<terms>"`) |
| Empty | Check `agent_states/` for active/paused cycles. If none: read `feature_idea_on_empty` from `.omp/agent-config.md` Cycle Options. If true, read the Feature Ideas path from config (default `documentation/FEATURES.md`) and present any unstarted items — offer to start a cycle for one, or run `/feature-idea` to capture a new idea. If FEATURES.md doesn't exist, has no unstarted items, or `feature_idea_on_empty` is false, ask for a feature description. |

Create/update state file immediately after determining entry point.

**Then resolve the depth, before Phase 1A** — `--mode` if given, else the story's `Depth` board
field, else the 5.6.4 heuristics, else ask (§ Depth is a property of the story). Write both
`Mode:` and `Mode source:` into cycle state's `## References` at this point. Resolving it later
is too late: the mode decides whether Phase 1A spawns `create-prd` at all.

**Checkpoint recovery (omp).** Under omp, you can checkpoint your session before risky operations (escalation ladder L3 revert, mid-cycle scope changes, complex merges). If the operation fails, `rewind` to the checkpoint instead of restarting the cycle:
```
checkpoint(action: "set", label: "pre-L3-revert-task-2.0")
# ... attempt the operation ...
# if it fails:
rewind(to: "pre-L3-revert-task-2.0")
```
This is faster than resume-from-state-file when the failure is recent and the state file hasn't been updated yet. Use checkpoints at: before each escalation ladder step, before mid-cycle scope changes, before complex dependency-order merges.

**Phase tracking (todo tool).** Initialize the `todo` tool with the pipeline phases as a visible progress tracker. Mark each phase `in_progress` when entering, `done` when complete. This gives the user real-time progress in the TUI alongside the cycle state file:
```
todo(op: "init", items: ["Phase 1A — Create PRD", "Phase 1C — Gate 1", "Phase 2 — Generate tasks", "Phase 2B — Gate 2", "Phase 3 — Implementation", "Phase 4A — Wrap-up", "Phase 4B — Release"])
```
On resume, re-initialize and mark completed phases `done` before continuing.

---

## Mode-conditional phase routing (5.6.1)

Before entering Phase 1A, route per the active `--mode`:
- **`full`** — all phases run as written below.
- **`lean`** — skip `create-prd` spawn in Phase 1A; derive AC inline from the feature description and store under cycle state `## References` → `AC summary:`. Skip Phase 1C (folded into Phase 2B). Phase 2 still spawns `generate-tasks` (with the inline AC summary as input). Phase 2B presents AC + tasks together for one combined approval.

  **First, ground the issue against the base.** An issue is a claim about the code as it stood when
  someone filed it, and the base has moved since. `grep` every symbol, file and "currently X" the
  issue names, against `[base]`, before deriving a single criterion. Where the issue and the code
  disagree, the code is right and the issue's premise is a finding — record it and derive AC from
  what is there. Measured in fan-out 7: #406's suggested test asserted that neither use case
  appeared in either file, which #403 had made false a week earlier; a lean cycle deriving AC
  verbatim would have shipped a red test, or "fixed" a sanctioned shortcut back out. This costs one
  grep and it is the cheapest check in the phase.

  **Read `.claude/skills/ac-authoring/SKILL.md` before deriving that AC, and apply it.** It is
  marked `disable-model-invocation`, so read the file — do not expect it to load itself. `create-prd` loads it on
  the `full` path; skipping the spawn skipped the rules too, and the rules are where the failures
  are. Measured in fan-out 4 (#443): the orchestrator wrote an AC naming a private field —
  `_hasLoadedProgramsOnce` is the *sole* gating signal — which `ac-authoring` rule 1 rejects
  outright ("observable, not an internal implementation detail"; its own bad example is "the search
  function calls the repository"). `coding-1.0` implemented it faithfully and produced a blank pane.
  The same skill's requirement that every feature carry `(-)` criteria, and its empty-state coverage
  category, are pointed straight at the remount case the AC set also missed.

  Deriving AC inline does not make it a lesser artifact. It is the same contract with the same
  agents reading it — only the author changed.
- **`hotfix`** — skip Phases 1A, 1C, 2, 2B entirely. Treat the feature description as a single implicit task. Go directly to Phase 3 with one agent, no isolation (`isolated: false`), no pre-digest. Phase 4A runs verify (lite depth) only.

## Phase 1A — Create PRD

Spawn the `create-prd` agent (model: sonnet) with the feature description. The agent explores the codebase, checks the roadmap, scans existing PRDs, and returns a complete PRD draft and file path.

Run **Context Sources retrieval** for stage `prd` (see § Context Sources retrieval) — results go to `local://ctx-sources.md`.

```
task(agent: "create-prd", context: "Create a PRD from the feature description.",
  tasks: [{ id: "create-prd", role: "PRD author",
    assignment: "Feature: [description]. [Any roadmap story number or context]. Read local://ctx-sources.md if it exists for context-source data." }])
```

Confirm the PRD file exists at the agent's `produces:` path. Missing = re-spawn or escalate.

Review the returned PRD for completeness, then proceed to Phase 1C.

Update state → Phase 1C.

## Phase 1B — Review existing PRD

Present sections one at a time for confirmation:
1. User Stories → confirm → apply changes
2. Functional Requirements → confirm → apply changes
3. Acceptance Criteria → confirm → apply changes

Update state → Phase 1C.

## Phase 1C — Gate 1

Summarize PRD (3–5 bullets: problem, stories, scope). Ask: **"Proceed to tasks?"**

End the message with the tag `<!-- gate:gate-1 -->` (see § Tagging a gate).

Approved → Phase 2. Changes → apply, re-ask.

## Phase 2 — Task generation

Spawn the `generate-tasks` agent (model: sonnet) with the PRD file path. The agent assesses the codebase, decomposes the PRD, and returns a complete task file and path.

Run **Context Sources retrieval** for stage `tasks` — results go to `local://ctx-sources.md`.

```
task(agent: "generate-tasks", context: "Decompose the PRD into implementation tasks.",
  tasks: [{ id: "generate-tasks", role: "Task planner",
    assignment: "PRD: [prd-file-path]. Read local://ctx-sources.md if it exists for context-source data." }])
```

Confirm the task file exists at the agent's `produces:` path. Missing = re-spawn or escalate.

Existing task file → present for review instead of re-generating.

## Phase 2B — Gate 2

Present task list. Ask: **"Begin implementation?"**

In `--mode lean`, **also present the inline AC summary above the task list** — this is the consolidated 1C+2B gate. One combined approval covers both AC and tasks. Three things the lean presentation must include, because this gate is the only review the inline AC gets:

- **Both `(+)` and `(-)` criteria, marked as such.** An all-`(+)` set is incomplete per `ac-authoring` and is the shape that ships blank-state regressions.
- **One scenario these criteria do not cover**, named in a sentence. Not a disclaimer — a specific sequence, state, or input the AC set is silent about, and whether you judge it in or out of scope. If you genuinely cannot name one, say that; it is a claim the reader can push back on.
- **Any criterion that names a private field, method, or internal flag**, flagged for rewrite before approval. That is `ac-authoring` rule 1, and it is the one that failed.

**Why this gate carries more weight in lean.** In `full`, AC is drafted by `create-prd` — a second agent reading the feature independently — and then reviewed by a human at Gate 1. `lean` removes the independent reading and keeps only the human. That is a real reduction, and fan-out 4 is what it cost: two regressions in code that was otherwise correct, both traceable to the inline AC rather than to any implementing agent. `verify` then passed 11/11, because verify audits coverage of *stated* criteria and structurally cannot see a criterion that was never stated; `review` caught it by reasoning from the code outward. A run report reading `verify: PASS 11/11, 0 NO IMPL` looked like a comprehensively validated cycle and was not.

The three requirements above do not restore the independent reading. They make the gap visible to the one reviewer lean still has.

**Immediately above the question, under the heading `### #<n> <issue title> Summary`, summarise it
in at most two paragraphs.** The heading carries the issue number and its real title verbatim —
`### #303 Fix Failing Tests Summary` — so the reader knows which window they are in without
scrolling. Not the AC, not the plan — the *issue body*, in your own words. Two parts, both
required, in this order:

1. **What it asks for**, and any constraint it states.
2. **Whether its premise still holds against the base** (§ Phase 1A) — and if anything in it has
   gone stale, what. That is the one fact the reader cannot get by opening the issue themselves.

The heading is not decoration. Round 9 ran this rule four times: all four cycles wrote issue prose
next to the prompt, two gave it a heading, and one delivered part 2 without part 1 — a staleness
note for an issue whose ask was never restated. Unlabelled prose is also why the first measurement
of this scored it 0 of 4: the gate log truncates its excerpt, and a summary that goes last is
invisible to anything sampling the top of the message. A named section is checkable; a paragraph
in the right place is not, and a heading without the number and title does not say which of five
open windows this gate belongs to.

It goes last, next to the prompt, so the reader has it in view while deciding. The reader is
approving AC derived from a body they would otherwise have to leave the terminal to read, and under
a fan-out they are doing that five times across five windows. Fan-out 8's two feature issues were
three-sentence stubs whose entire content would have fitted in a sentence of this summary.

End the message with `<!-- gate:gate-2 -->`, or `<!-- gate:gate-1+2 -->` in `lean` (see § Tagging a gate).

Approved → create feature branch, update state, Phase 3. Changes → apply, re-ask.

### Reading a suite result

**Never run the test command into your own context, and never trust a pipe to
bound it.** In v0 run 2 a `| tail -5` still delivered 22,819 characters, twice,
to learn that 81 tests passed. Every suite run, scoped or full, goes through:

```sh
python3 .claude/skills/cycle/suite-result.py run <name> -- [Run all tests command]
python3 .claude/skills/cycle/suite-result.py check <name>   # started by run-suite.sh
```

One line back — `SUITE <name> PASS tests=3891 failed=0 elapsed=110s log=<path>`
— plus up to 15 failing test names when red. Full output stays at `log=`.

**Exit 0 passed, 2 failed, 3 running, 4 unparseable.** Branch on the code, not on
truthiness. **4 is not 2 and not 0**: no pack pattern matched this reporter, so
report that rather than inferring a verdict — the fix is a row in
`.claude/packs/<pack>/suite-patterns.md`, not a guess here.

### Tagging a gate

**Every message that ends awaiting a human decision must end with `<!-- gate:NAME -->`.** It is an
HTML comment, so it does not render; the `gate-log.py` Stop hook reads it from the transcript and
writes `NAME` into the gate log.

Use the name of the gate being raised — `gate-1`, `gate-2`, `gate-1+2`, `gate-4b`, `pr-merge`,
`scope` — or a short descriptive slug for an ad-hoc question.

The hook falls back to matching the text when the tag is absent, and that fallback is why the tag is
required. Across fan-out 2, 3 and 4 it named **no** gate correctly: its patterns were keyed to this
skill's own wording — "proceed to tasks?", "begin implementation?" — and the orchestrator writes
"## Gate 1C+2B (lean — consolidated)" or "**4B is blocked.**" instead. The only label it ever
produced was a false positive. Six real gates totalling 1h02m in fan-out 4 were reported as *"none
classified as a gate"*, which reads as nobody having waited.

Do **not** tag a message that ends because you are waiting on an agent — that is not a gate, and the
hook already classifies it from the wakeup that ends it.

---

## Phase 3 — Implementation

You delegate and track. You do not write code. If you ever complete work that should have gone through an agent (e.g., applying a trivial fix to the feature branch yourself), emit `RESCUE manual-completion [task-id]: [what you did] | resolution: [why] | artifact: [commit hash or path]` to monitor — silent substitutions destroy the audit trail.

**Mid-cycle scope changes.** If after Gate 2 you add, remove, or modify an acceptance criterion (e.g., the PRD missed a case discovered during implementation), emit `SCOPE_CHANGE [added|removed|modified] AC [ac-id]: [text] | reason: [why]` to monitor. `verify` reads this list and audits against the current truth, not the frozen PRD.

### Analyzer baseline (5.8.1)

If `analyzer_baseline` in `.omp/agent-config.md` § Hygiene flags is `soft_warn` or `hard_fail_if_exceeded`, capture the baseline at Phase 3 start by running the **Analyze / lint** command from `.omp/agent-config.md` § Project Commands and redirecting its output:

```
<analyze-lint command> 2>&1 | grep -E '<analyzer_finding pattern>' \
  > agent_states/analyzer-baseline-<feature>.txt || true
```

**Capture the finding lines, not the whole output**, using the `analyzer_finding` pattern from
`.claude/packs/<active-pack>/analyzer-patterns.md`. `flutter analyze` prints
`No issues found! (ran in 5.4s)` — the elapsed time is in the output, so a whole-file diff is
non-empty on every run even when both sides have zero findings, and under `hard_fail_if_exceeded`
that forced REQUEST CHANGES on every cycle regardless of the code. Filtering at capture time means
the Phase 4A diff needs no special handling: an empty baseline and an empty current are equal.

**`agent_states/`, not `cycle_reports/`.** The baseline is scratch with a lifespan of one cycle:
written at Phase 3 start, read once at Phase 4A, meaningless afterwards. `cycle_reports/` is a
permanent record and, where a vault is configured, a *shared* one — so a baseline written there is
never consumed and never pruned. One deployment accumulated 61 of them, plus 59 directories that
existed only to hold one. The bytes are small (~159 KB); the problem is permanence and noise in a
repository holding several applications' history. `agent_states/` is gitignored, is
per-clone under a fan-out, and is what `clear-agent-states.py` exists to empty.

Phase 4A re-runs the same command and diffs. New warnings in the diff:
- `soft_warn` → flagged in the run report under a new "Analyzer drift" section; cycle proceeds.
- `hard_fail_if_exceeded` → review verdict flips to REQUEST CHANGES regardless of other findings; the diff is included in the review report.

### Known pitfalls (5.8.3)

Per parent task, before spawning its implementation agent, ask which entries match that task's **Relevant Files** — do not read the file:

```sh
python3 .claude/skills/cycle/pitfalls.py lib/data/foo_repository.dart test/data/foo_test.dart
```

It returns the `## Known pitfalls for files you'll touch` section ready to paste into the spawn prompt, `hard` preface included. Exit 0 attach it, **1 attach nothing**, **3 no pitfalls file** — optional configuration, not a finding, so don't report it as a gap. `--files-from -` takes the Relevant Files list on stdin.

Reading the file costs ~5,200 tokens whatever matches, because it grows with the project's bug history rather than with the task.

`unparsed:` lines name entries that can never match — a missing `Globs:` or `Body:`. Surface them in the run report: a pitfall that silently stopped applying is the failure the mechanism exists to prevent. An unreadable `Severity:` reads as `hard`.

File format, which the project owns:

```markdown
## <Short title>
Globs: src/**/Infrastructure/**, tests/**/Data*
Severity: warn | hard
Body:
[One paragraph describing the pitfall and how to avoid it. Cite a real incident if available.]
```

### Compact at phase boundaries (5.8.2)

If `auto_compact_at_boundaries` in `.omp/agent-config.md` § Hygiene flags is `on`, invoke `/compact` at:
- **Phase 2→3 transition** — after Gate 2 is approved, before any Phase 3 spawn.
- **Phase 3→4A transition** — after the last parent task merges, before the Phase 4A wrap-up runs.

Compaction reclaims context but can cost orchestrator decision-continuity; keep `off` until telemetry shows the trade-off is favorable for your cycles.

### 3.1 — Pre-flight

Check `.claude/agents/scaffold/` for project-specific pattern files (files with `Type: project-specific`). If none exist and the task list includes scaffold-type work, autonomously spawn a setup-scaffold agent:

```
task(agent: "explore", context: "Run the /setup-scaffold skill in scan mode.",
  tasks: [{ id: "setup-scaffold", role: "Pattern discovery",
    assignment: "Read .claude/skills/setup-scaffold/SKILL.md and follow its steps. Do not ask the user questions — use your best judgment for pattern discovery and create all pattern files you find. Report what was created." }])
```

Run this in the background — it does not block Phase 3 from continuing. Scaffold agents spawned later will pick up the pattern files once they exist.

Initialize state persistence per **§ State persistence**: by default (`agent_messaging: false`) write the state file inline — no agent spawned. Only when `agent_messaging: true`, spawn the background monitor here (model: monitor row from **Model Allocation** table in `.omp/agent-config.md`).

**The supervisor (item 5.5.1)** runs distinct from monitor (monitor: deterministic state archival; supervisor: heuristic observation). OQ-9 (consolidation) is deferred pending real telemetry.

The supervisor is **not** a long-lived daemon and needs **no** agent-messaging. The orchestrator drives it by spawning a fresh, short-lived check per cadence tick (below); each spawn does exactly one check for one agent and exits, with continuity persisted on disk in `agent_states/supervisor/state.md`. This is what makes supervision work in environments without the irc tool / agent-teams.

**The supervisor requires omp. Under Claude Code it does not run** — see § Cadence under
Claude Code for why the mechanism cannot work there. Skip it for the whole cycle and log
`SUPERVISOR_HEALTH status:disabled spawns:0 stalls:0 heartbeat:none disabled_at:[ts] reason:harness-unsupported`.
Do not spawn checks, do not maintain counters, and do not treat the absence as a fault.

**Skip the supervisor entirely** when the task file has fewer than `skip_supervisor_if_total_subtasks_lt` sub-tasks (Per-phase skip flags in `.omp/agent-config.md`, default 3) — observation overhead exceeds value on small task lists. Log the skip as `SUPERVISOR_HEALTH status:disabled spawns:0 stalls:0 heartbeat:none disabled_at:[ts] reason:skip-flag` so the run report reflects it.

**Cadence — when to spawn a check.** No messaging required; it's control-flow driven. The orchestrator spawns a `CHECK <agent-id>` at these triggers:
1. **On wave boundary** — after spawning a parallel wave, and each time control returns from a completing background agent, spawn a check for every *still-active* agent-id. This catches mid-run `spiral` / `stall` / `drift` while other agents keep working.
2. **On agent completion** — when a Phase-3 implementation agent returns, before its task branch is merged, spawn a final check for that agent-id (catches `shallow` / `drift` on the finished output).

Each check is a short **foreground** spawn: the orchestrator waits for the one-line summary, then drains any escalations via `irc(op: "inbox")` and acts on `pause-request` / `depth-recommendation` per the escalation ladder (5.5.4). Maintain a `supervisor_checks` counter and a `supervisor_check_failures` counter in cycle state — they feed the run report and the health watchdog below.

```
task(agent: "supervisor", context: "CHECK [agent-id]. One check per spawn.",
  tasks: [{ id: "supervisor-<tick>", role: "Supervisor check",
    assignment: "CHECK [agent-id]. Feature: [name]. Cycle state: agent_states/cycle-state-[name].md. Agent ID convention: <role>-<task-number>. Do exactly one check per supervisor.md, then exit." }])
```

The supervisor sends whispers via `irc` to implementation agents and escalations via `irc` to the orchestrator. It writes `agent_states/supervisor/state.md` (ladder state) and touches `agent_states/supervisor/heartbeat`. It reads the agent's omp session transcript (`history://<agent-id>`) and `agent_states/cycle-state-*.md`.

**Artifact layout (Phase 3):**

```
agent_states/
  cycle-state-<feature>.md       # orchestrator writes inline (monitor if agent_messaging)
  supervisor/state.md            # supervisor writes (ladder + last_check)
  supervisor/heartbeat           # supervisor touches
```

Whispers and escalations travel via irc — no file artifacts. Agent transcripts (`<id>.jsonl`) live in the omp artifacts dir.

### 3.2 — Dependency analysis

Classify parent tasks: **independent** (start now) or **dependent** (wait for prerequisite).
Classify sub-tasks by type → assign agent per the delegation table in 3.3.

Present analysis in dry-run mode. In `--exe` mode, proceed.

### 3.3 — Spawn agents

Before spawning any implementation agent:

1. **Extract file paths** from the task file's "Relevant Files" section — pass these per-agent in each `assignment`.
2. **Extract AC** from the PRD's Acceptance Criteria section — write to `local://ac.md`. Test and verify agents read it; implementer reads it.
3. **Run Context Sources retrieval** for stage `implement` once per parent task — write results to `local://ctx-sources.md`. Implementer and test agents reference it.
4. **Write `local://prd.md`** with the PRD path + feature description. Any agent that needs PRD context reads it.

#### Parallel task waves (batch mode)

For **independent** parent tasks, spawn them as a batch — one `task` call with a `tasks[]` array. Each item gets its own `id`, `role`, `assignment`, and `isolated: true`. The `context` field is left minimal (omp requires it for batch mode but it raw-injects into every system prompt — keep it to a one-liner). Shared background lives in `local://` files that each agent reads on demand:

```
task(
  agent: "<kind-agent>",        // scaffold, ui-story, coding, or task
  context: "Read local:// files referenced in your assignment for shared context.",
  tasks: [
    { id: "scaffold-1.0", role: "Scaffold engineer (task 1.0)", isolated: true,
      assignment: "Sub-tasks: [list]. Relevant files: [paths]. Read local://prd.md and local://ac.md for PRD context. Read local://digest-1.0.md if it exists. Read local://ctx-sources.md for context-source data." },
    { id: "coding-2.0", role: "Software engineer (task 2.0)", isolated: true,
      assignment: "Sub-tasks: [list]. Relevant files: [paths]. Read local://prd.md and local://ac.md. Read local://digest-2.0.md if it exists. Read local://ctx-sources.md." },
    ...
  ]
)
```

The session semaphore bounds concurrency. Each isolated agent gets its own workspace from the feature-branch HEAD (pinned explicitly under Claude Code — see § Phase-3 isolation); its task branch merges when the agent completes.

For **dependent** tasks, wait for the prerequisite's isolated agent to complete and omp to merge its branch, then spawn the dependent task (it forks from the updated HEAD automatically).

#### Per-task agent sequence

For each parent task (whether batched or sequential), the sequence is:

**Skipping a step the flags say to run.** The skip flags below are the rule; your judgment may still
be better on a given task, and overriding them is allowed. **Record it when you do**, as one line in
cycle state:

```
SKIP [agent] [task] reason: <why this task did not need it>
```

Without that line the override is invisible — it reads as the flag having fired, and `self-improve`
counts flag behaviour it can only read from prose. Measured in fan-out 7: two Phase-3 skips were
orchestrator judgment against the configured flags, both defensible, neither recorded, and the only
trace was a sentence in a run report. A flag that is quietly overridden is a flag nobody can tune.


1. **Pre-digest** (`pre-digest` agent, background job) — default for any task touching ≥ `skip_predigest_if_files_lt` existing files (default 2). Spawn all independent tasks' pre-digests as parallel background jobs, then collect via `job poll`:
   ```
   task(agent: "pre-digest", context: "",
     tasks: [{ id: "predigest-1.0", role: "Pre-digest (task 1.0)", assignment: "Files: [paths]. Write your digest to local://digest-1.0.md." },
             { id: "predigest-2.0", role: "Pre-digest (task 2.0)", assignment: "Files: [paths]. Write your digest to local://digest-2.0.md." }])
   ```
   **Spawn the named `pre-digest` agent, and give it the path to write.** It holds `Write` and places
   its own digest; collect the path it returns, do not transcribe its output. Fan-out 6 spawned a
   read-only agent for this instead — the skill said "generic haiku agent", which names nothing a
   Claude Code orchestrator can spawn — and both digests came back as *"Since I'm in READ-ONLY mode,
   I cannot write files, but here's the complete information formatted for you to save"*. The
   orchestrator pasted them by hand: orchestrator context spent copying, and a digest silently
   re-authored in transit. The implementation agent's `assignment` references the file.

2. **Implement** — dispatch by the parent task's `[kind: …]` tag:

   | `kind` value | agent |
   |---|---|
   | `scaffold` or `scaffold-*` | `scaffold` |
   | `ui-story` | `ui-story` |
   | `test` | `test` |
   | `coding` | `coding` |
   | `task (generic)` | `task` |

   Each implementation agent spawns with `isolated: true`, `id: "<kind>-<task-number>"`, `role: "<role> (task <task-number>)"`. The `assignment` carries the sub-task list, relevant files, and `local://` file references. The agent reads only what it needs.

   For `scaffold-*` kinds, pass the pattern name in the `assignment` so the agent loads `.claude/agents/scaffold/<pattern>.md`.

   - **You** mark sub-tasks `[x]` as agents report them — the task file is runtime and is not in the agents' workspaces (see § Gitignore guard). State this in the spawn prompt so the agent reports completions instead of hunting for a file to tick.
   - On failure/ambiguity: report to orchestrator, continue independent sub-tasks
   - The task branch merges into the feature branch on completion (omp automatically; manually under Claude Code)

3. **Pre-flight** (sonnet, after implementer merges, before test agent). Skip when `skip_preflight_if_no_existing_tests` is `true` and grep of the **Test path glob** for any public symbol the implementer touched returns no hits. The pre-flight agent needs ONLY changed source files + base ref — no shared context files:
   ```
   task(agent: "test-preflight", context: "Classify existing tests for changed symbols.",
     tasks: [{ id: "preflight-<task-number>", role: "Pre-flight classifier (task <n>)", isolated: true,
       assignment: "Changed source files: [paths]. Base ref: feature/[name]." }])
   ```
   The classifier returns a `## Existing test classifications` table. Lift it into the test
   agent's `assignment`.

   **A `keep` verdict is a hypothesis, not a finding.** It has been wrong twice, in different
   ways. It reported existing view-model tests already covered new scoping behavior when every
   stub used `any(named: 'x')`, which matches `null` too. And in fan-out 4 it returned **47/47
   `keep`** with two wrong, one of whose stated reasons described its own vacuity exactly — the
   test passed because the change had removed the widget it asserted about, so nothing could ever
   make it fail. An orchestrator override was all that stood between that and a green cycle.

   Each `keep` must cite a `file:line` assertion **and** say what would have to change for the
   test to start failing. Pass any `keep` that does neither to the test agent as `update`
   instead, and let the test agent's forced-falsification step settle it. Treat an all-`keep`
   return as a prompt to check the two or three tests closest to the changed symbols yourself
   before lifting the table.

   Raised from haiku to sonnet after fan-out 4, alongside the two rule changes above — so if this
   stops recurring, which of the three fixed it is not separable. The gate's output is consumed
   blind by the test agent and an error here surfaces two stages later, if at all, which is what
   argued for the more capable model rather than only the cheaper rule changes.

4. **Test** (separate agent from implementer; gets a fresh isolated workspace from the updated feature-branch HEAD after the implementer's merge). The test agent reads `local://ac.md` and `local://ctx-sources.md` but does NOT need the digest:
   - **Write**: `task(agent: "test", context: "Write tests for the implemented feature.", tasks: [{ id: "test-<n>", role: "Test engineer (task <n>)", isolated: true, assignment: "Source files: [paths]\nTest files: [paths]\nTask: [desc]\nRead local://ac.md for AC. Read local://ctx-sources.md for context-source data.\n[pre-flight table]" }])`
   - **Fix**: re-spawn `test` agent with failure output and source paths

### 3.4 — Handle results

- **Success**: capture the agent's `## Deviations` section — forward each to monitor (`DEVIATIONS [task-id] AC [ac-id]: [what] | reason: [why]`). Under omp the task branch is already merged into the feature branch (branch-mode merge on isolated agent completion); under Claude Code, merge it yourself. Verify the merge is clean: **Analyze / lint** inline, and the test suite through `run-suite.sh` rather than inline — `bash .claude/skills/cycle/run-suite.sh start merge-[task-id] -- [Run all tests command]`, then read the verdict with `python3 .claude/skills/cycle/suite-result.py check merge-[task-id]` before spawning the next task (see § Reading a suite result). This fires after **every** sub-task, so it is the most frequent full-suite run in a cycle and the one that most needs the cross-clone lock: under fan-out, unlocked runs here are what stretch a 2m39s suite past eight minutes (evidence-run2 F1). Send status to monitor.
- **Failure**: escalation ladder (below)
- **Contradiction-exit** (agent's return contains `status: contradiction-exit` per the `contradiction-exit` skill — item 5.4.4): emit `RESCUE contradiction-loop [task-id]: [trigger value] | resolution: human escalation | artifact: [report path or "agent return"]` to monitor, then jump to **L4** immediately. Do **not** run the escalation ladder for L1–L3 — the agent already exhausted its retries by construction. Preserve the structured block verbatim in the user-facing message.
- **Stalled** (agent killed by the harness watchdog, or returns no clean result): run **Stall salvage** (below), then the escalation ladder using the salvage assessment as context
- **Blocked**: notify user, continue independent tasks

### Supervisor cadence (5.5.4)

The supervisor runs **under omp only**. The cadence mechanism decides when a check is due from
how tool calls are counted, and only omp can attribute them to the right agent.

#### Cadence under omp

The task tool's async job progress and the agent registry status (`running` / `idle` / `parked`) replace the counter files. At your watchdog tick (and at each sub-task boundary), check `irc(op: "list")` for live agents. For each agent that has been `running` long enough to exceed the cadence threshold (default 5 tool calls — approximate via transcript length: read `history://<agent-id>` and count tool-call entries), spawn a supervisor check:
  ```
  Spawn the `supervisor` agent (model tier: [supervisor row from Model Allocation], resolved per harness per § Configuration, id: "supervisor-<tick>") with this prompt:
  > CHECK <agent-id>. Feature: [name].
  ```
- After spawn returns, drain any escalations via `irc(op: "inbox")`.
- **Skip cadence checks entirely if supervisor health Status is `disabled`** (degraded mode — see below).

Supervisor spawns are fresh per check — continuity lives in `agent_states/supervisor/state.md`. The escalation channel below is how the supervisor signals back to you.

#### Cadence under Claude Code — the supervisor is disabled

Do not spawn supervisor checks under Claude Code. Set supervisor status to `disabled` with
`reason:harness-unsupported` at Phase 3 start and continue the cycle without supervision.

The counter path this section used to describe does not work, and shipping it produced worse
outcomes than no supervisor at all: a cycle with 25 sub-tasks across six implementation agents
spawned exactly **one** check, on the first agent's completion, and reported itself supervised.

The mechanism breaks on agent identity. The PostToolUse hook writes counters keyed by the
harness's own agent id, while cadence needs the `<role>-<task-number>` label — and Claude
Code's `Agent()` call has no `id` field to set one. The orchestrator first learns an agent's
harness id from its **spawn return**, which is exactly when a mid-run signal is no longer
actionable. So `spiral`, `stall` and `drift` can only ever fire after the run they were meant
to interrupt.

Reinstating this needs an id it can address before the agent finishes: an orchestrator-supplied
label the hook writes counters under, or a spawn-time label→agentId mapping recorded in cycle
state. Until one exists, a disabled supervisor is the honest configuration — an enabled one
that checks once per cycle is a quality gate the run report will claim you had.

### Supervisor health (5.5.5)

Six layered mechanisms, evaluated as you spawn and collect each check (the cadence above):

1. **Last-check record (not a liveness watchdog).** The supervisor touches `agent_states/supervisor/heartbeat` at the end of every successful check. Because checks are intermittent *by design*, a stale heartbeat is **not** an outage signal — never treat heartbeat age as "offline." Record the heartbeat mtime as the supervisor's `last_check` for the run report. Liveness is judged per-check by mechanism 2.
2. **Per-check spawn watchdog.** When you spawn a `CHECK <agent-id>`, treat the spawn as failed if it errors or does not return a summary within 30s. Increment `supervisor_check_failures`, emit `RESCUE supervisor-stall [supervisor]: check [agent-id] no return in [N]s | resolution: skip-or-disable | artifact: agent_states/supervisor/state.md` to monitor, and skip this tick's result.
3. **Rescue logging on outage.** Already provided by (2) — `supervisor-stall` is in the rescue type enum.
4. **Circuit breaker.** Maintain the **Supervisor health** section in cycle state (via monitor's `SUPERVISOR_HEALTH` verb). If `supervisor_check_failures` increments 3 times within a 5-minute window, **disable** the supervisor for the rest of the cycle: emit `RESCUE supervisor-disabled [supervisor]: 3 check failures in 5m | resolution: degraded mode | artifact: cycle-state` and forward `SUPERVISOR_HEALTH status:disabled spawns:[n] stalls:[n] heartbeat:[last] disabled_at:[now] reason:circuit-breaker`. Stop spawning supervisor checks; the cycle continues in degraded mode (no whispers, no escalations — falls back to today's behavior).
5. **Run-report check success rate.** When you build the cycle run report at Phase 4A, populate the **Supervisor health** subsection of the Agent Telemetry block from cycle state: `supervisor_checks` attempted, `supervisor_check_failures`, and success rate. Classify the cycle as **degraded** if success rate < 90% or status is `disabled`.

7. **Zero-spawn check — an error condition, not a footnote.** Applies under omp only; a Claude
   Code cycle records `status:disabled reason:harness-unsupported` and is not degraded for it.
   At Phase 4A, if the supervisor was enabled (not skipped by flag, not disabled for the
   harness, not circuit-broken) and `supervisor_checks == 0`, the
   supervision path did not run at all. **Surface it to the user in the 4A output**, emit
   `RESCUE supervisor-never-ran [supervisor]: enabled but 0 checks across [n] agents |
   resolution: [what you found] | artifact: cycle-state`, and mark the cycle degraded.

   Do **not** write a justification into the run report and move on. Zero spawns with the
   supervisor enabled means the cadence mechanism for your harness was never exercised — the
   most likely cause is an unwired PostToolUse hook or a cadence threshold no agent reached.
   Diagnose which, and say which.

   **A ratio, not a floor.** One check across six agents passes `> 0` while supervising almost
   nothing. Compare `supervisor_checks` against the number of agents that ran: fewer than one
   check per active agent is itself worth surfacing, even though it clears the zero test.
6. **`self-improve` hook.** Documented in `.omp/agents/self-improve.md` Step 2 (Effectiveness patterns → Supervisor health). When `supervisor-stall` or `supervisor-disabled` appears in ≥ 3 of the last 5 cycles, `self-improve` raises a P0 recommendation.

### Plan-revision flow (5.5.6)

When you process a `depth-recommendation` escalation, you decide — the supervisor only *recommends*. Three rules:

1. **Decide accept or reject** with a one-line rationale grounded in current cycle context (task progress, AC scope, escalation ladder state, time pressure). Examples: "accepted — task 2.0 has 3 unrelated sub-tasks per Relevant Files," "rejected — split would create cross-cutting test dependencies," "rejected — too late in Phase 3 to re-shape."
2. **Emit `SUPERVISOR_REC suggestion:[text] accepted:[true|false] rationale:[text]` to monitor** for every recommendation — accepted *and* rejected. Silent drops destroy the audit trail and starve `self-improve` of tuning data.
3. **If accepted, apply the change** within your existing primitives — re-spawn a task with a different model, split a parent task into two task-file entries, insert a verify pass, etc. The recommendation is not a pipeline-design override; the orchestrator still owns pipeline shape.

If a recommendation conflicts with a recommendation you accepted earlier (or with mid-cycle scope changes), prefer the later signal but record both decisions.

### Supervisor escalation polling

The orchestrator collects supervisor escalations at three moments only (item 5.5.2):
1. **Phase transition** — end of Phase 3, before spawning verify/review.
2. **Sub-task boundary** — after each parent task's Commit protocol, before spawning the next.
3. **After each supervisor check** — you've just collected a check's result (see 5.5.5: per-check spawn watchdog + circuit breaker), so drain any escalations it emitted.

**Under omp (default):** drain your irc inbox at each moment — `irc(op: "inbox")` returns all pending escalation messages from the supervisor. No cursor tracking needed (messages are consumed on read). See the `escalations` skill § Transport for the per-type handling (`pause-request` → recovery decision + `RESCUE`; `depth-recommendation` → log decision in cycle state; `bug-pattern` → log + surface in run report). For time-sensitive `pause-request` handling at watchdog ticks, `irc(op: "wait", from: "supervisor-<tick>", timeoutMs: 30000)`. Never block mid-tool-call.

**Claude Code fallback:** poll `agent_states/escalations.jsonl` with a per-cycle `escalation_cursor:` field tracking the last processed line.

**Agent-ID stamp.** Every Phase-3 implementation agent must be spawned with `id: "<role>-<task-number>"` (e.g., `id: "test-3.0"`, `id: "ui-story-2.1"`) in the task spawn. Under omp, this `id` field sets the child session's agentId — it becomes the irc address (supervisor sends whispers via `irc(op: "send", to: "test-3.0", …)`), the registry key, and the artifact filename (`test-3.0.jsonl`, `test-3.0.md`). The supervisor reads the agent's omp session transcript (`history://test-3.0` for concise view, or the `<id>.jsonl` artifact for full tool-call detail) instead of a hook-written event log. Under Claude Code, the PostToolUse hook routes events into `agent_states/events/<agent-id>.jsonl` — pass the agent-id in the spawn prompt text since Claude Code's Agent() call has no `id` field.

### Escalation ladder

Max 3 attempts per sub-task, 5 total per parent task.

| Level | Trigger | Action |
|---|---|---|
| L1 | Compile/analysis/simple test error | **Haiku** fix agent, 1 attempt |
| L2 | L1 failed or non-trivial error | Next model up with error + context |
| L3 | L2 failed | Revert changes, **opus** fresh attempt (anti-pattern: what failed) |
| L4 | All auto-recovery failed | Block, report to user, continue independent tasks |

Send every escalation to monitor: `ESCALATION [task-id] L[1-4]: [model] [reason]`

### Stall salvage

A stalled agent — one the harness watchdog kills before it returns cleanly, or one that exits with its expected artifact missing or still `IN PROGRESS` — must leave an audit trail, not be silently replaced by manual work.

On detecting a stall, spawn one inline Haiku salvage pass — do not analyze the stall yourself:

```
task(agent: "task", context: "Salvage only what is recoverable — do NOT redo its work.",
  tasks: [{ id: "salvage-<agent-id>", role: "Salvage pass",
    assignment: "The [agent role] agent for [task/feature] stalled. Inputs: [partial report path if any] and the git state (run git diff [base] and git log). Produce a PARTIAL — agent stalled artifact at [path]: record what completed, mark what is missing, assess whether the result is coherent. Return the artifact path." }])
```

Send `RESCUE stall [agent-id]: [agent role] stalled before finishing | resolution: ran Haiku salvage | artifact: [salvage report path]` to monitor. Then: for a stalled `verify`/`review`, the `PARTIAL` report feeds the 4A gate; for a stalled implementation agent, proceed via the escalation ladder with the salvage assessment as the "what was attempted" context.

### Bug tracking

Existing-code bugs (not agent-written code):
1. File a GitHub issue: `gh issue create --label bug --label severity:<high|medium|low>`.
   Title it plainly — **there is no `BUG-NNN` ID for new bugs.** Do not scan for a
   next ID and do not derive one from a title search; the issue number is the
   identity. (Bugs migrated from the old `documentation/bugs.md` keep their legacy
   token *and* carry their issue number, written `BUG-065 (#191)`.)
2. Note in cycle state, citing the issue number.
3. Don't fix unless blocking. If blocking: fix it, and add `Closes #<n>` to the PR body
   alongside the story's own. **Do not close it by hand** — the fix ships when the PR
   merges, and closing it now records it done while it is still unmerged. Same reason as
   step 9 (M31).

### Commit protocol

Per parent task, when all sub-tasks pass:
1. **Clean-check** — assert `git status --porcelain` in the main checkout is empty. The orchestrator writes no implementation code, so a dirty main checkout means something leaked: abort, report to the user.
2. Run test + typecheck/lint commands (from **Project Commands** in `.omp/agent-config.md`) in the main checkout, after the task branch is merged. **This is the full-suite run the agents no longer make** — they run scoped tests only (see the `test` agent § Running tests without being killed), so this gate is what actually catches cross-cutting breakage. Under a fan-out, start it with `run-suite.sh` rather than inline: the lock keeps concurrent cycles from fighting over one machine, which is what stretched an eight-minute suite past the watchdog.
3. **Silent-skip gate** — grep the diff of test files (`git diff [base]...HEAD -- '<test-glob>'`, where `<test-glob>` is the **Test path glob** from `.omp/agent-config.md` § Project Commands) for the regex patterns in the active pack's **Test anti-patterns** file. Any hit blocks.
   On hit: emit `RESCUE silent-skip [task-id]: [file:line + pattern] | resolution: re-spawn test agent | artifact: none` to monitor, then re-spawn the `test` agent (isolated) with the offending file + matched pattern. One retry; a second hit escalates per L3.
4. Green and gate clean → mark parent `[x]`, update monitor. Under **omp** the task branch is already merged and the workspace cleaned up — nothing manual. Under **Claude Code** neither happens on its own: merge the task branch, then `git worktree remove` its directory and `git branch -D` its branch. Leftovers are what the Phase-0 janitor has to sweep next run.
5. Red tests → escalation ladder from L1

Never auto-revert commits. Report to user with options.

### When no agent holds the permission a task needs

Under Claude Code each agent's `tools:` grant is static, so a task can be well-formed and still have
no agent able to run it. Fan-out 1 hit this: a task needed `dart run drift_dev schema dump` *and*
`git worktree add`, and no agent held both. It was resolved by the orchestrator doing the work
itself — which is the failure, not the fix. The run report then grades a cycle whose agent
boundaries were quietly not the ones the pipeline describes.

When you find a task no agent can execute, in this order:

1. **Split it.** Useless when *no* agent holds the grant — there is no half to hand off.
2. **Widen the grant** — usually closed under Claude Code: a deployment reaches agents through
   `~/.claude/agents`, so there is no local frontmatter, and editing the framework's copy
   mid-cycle is what `guard-framework.py` blocks.
3. **Escalate to the user** — the expected exit, not the last resort. Some work is legitimately
   human: placing a 1.85 MB dataset was, and `Write` is no substitute (it re-encodes the bytes,
   and that story's invariant was a missing trailing newline).

**Do not run it yourself.** An orchestrator absorbing agent work is `harness-findings` probe 10, and
it hides a permanent matrix gap behind a cycle that looks clean. Whatever you choose, record it in
the run report's Harness findings — the gap is a framework fault even when the work shipped.

The grants themselves are pinned by `tests/framework_checks.py` § phase-3 permissions. Under omp
this section does not apply: agents hold bare `bash`, so a task that fails here may well succeed
there, which is exactly why the failure has to be reported rather than absorbed.

**Do not brief an agent on what it cannot run.** The grant is a floor, not a ceiling — a
classifier may allow more, and not identically every time: two `coding` spawns minutes apart
disagreed about `shasum`, and the one that believed its briefing wrote a throwaway script
instead. Let agents try and report a real refusal.

### Dependencies

Agents do NOT add packages. On need:
1. Agent pauses, reports to orchestrator (what, why, alternatives)
2. Orchestrator evaluates
3. If justified → present to user for approval
4. Approved → install the package using the project's package manager

### Usage limits

Signals: explicit warnings, tool failures, truncation, very long session.

1. Finish current in-flight agent only
2. Pause signal to monitor (include worktree paths, current task)
3. Schedule auto-resume — under **Claude Code** use `CronCreate` (durable, one-shot, offset from round marks); under **omp** there is no built-in scheduler, so resume manually with `/cycle --exe agent_states/cycle-state-[name].md`
4. Report to user: what's done, resume point, manual fallback command

---

## Phase 4 — Completion

Two parts: **4A** runs immediately with no user interaction. **4B** runs when the user returns after verify/review (or says to proceed now).

### 4A — Wrap-up (MANDATORY — execute immediately, do not stop or ask; step 7 MUST execute even if the user skips 4B)

1. Run test + typecheck/lint commands from **Project Commands** in `.omp/agent-config.md` (final full suite). **Analyzer drift check (5.8.1):** if `analyzer_baseline` is `soft_warn` or `hard_fail_if_exceeded`, diff the current analyze output — **filtered through the same `analyzer_finding` pattern used at capture** — against `agent_states/analyzer-baseline-<feature>.txt` recorded at Phase 3 start (older cycles wrote it to `cycle_reports/<feature>/analyzer-baseline.txt`; if that is all you find, use it and note the stale path). Append the diff (or "None") to the run report's `## Analyzer drift` section. **If no baseline file exists, write "Not recorded — no baseline captured at Phase 3 start" rather than "None".** A missing baseline and a clean diff are different facts, and `agent_states/` is cleared between cycles, so the file genuinely can be absent. Under `hard_fail_if_exceeded`, force the review verdict to REQUEST CHANGES if the diff is non-empty.
2. Mark ALL tasks and sub-tasks `[x]` in the task file (final sweep)
3. Generate cycle report → `cycle_reports/[feature-name]-[YYYY-MM-DD].md`:
   - Summary (what was implemented, per parent task)
   - Branch name, commits (hash + message), database/schema changes (or "none")
   - Bugs discovered, known limitations, blocked tasks, follow-up items
   - Deviations from PRD AC (copy the cycle state's **Deviations** section verbatim; write "None" if empty)
   - Scope changes (copy the cycle state's **Scope changes** section verbatim; write "None" if empty)
4. Present cycle report to user inline
5. Generate run report → `agent_tasks/reports/report-prd-[feature-name]-[YYYY-MM-DD].md` using template `.claude/skills/cycle/report-template.md`. **Agent Audit**, **Rescues**, and **Agent Telemetry** sections are required. Copy the **Rescues** list from the cycle state file verbatim into the run report's `## Rescues` section (write "None" if cycle state has no rescues). For **Agent Telemetry**, run `python3 .claude/skills/cycle/aggregate-telemetry.py` (or `~/.claude/skills/cycle/aggregate-telemetry.py`, whichever resolves) and paste its output into the section — it emits the table rows and the Phase-3 totals block ready to use. **Run it after step 6, not here** — `verify` and `review` have not been spawned yet at this point, so a table collected now omits the cycle's two most expensive agents by construction. Fan-out 6: a `review` that made 20 tool calls had no row at all, and two of four clones reported this independently. Write the rest of the report in order and come back for **Agent Telemetry**, **Gate wait** and **Permission prompts** once step 6 has returned. **Do not read `agent_states/events/` yourself.** Under a fan-out, finalize archives each clone's events and gate log to `<clones-root>/telemetry/<clone>/` before clearing them, so the cross-clone questions stay answerable after every cycle has ended — point the aggregator at those with `--events`. Measured, that directory is ~175× the size of the table it produces, and one deployment reached 966 files where the raw read exceeds a context window — which is why reports in that vault say telemetry was not collected. The script handles the empty and missing cases with the template's own wording, and prefixes a warning when agent ids have collapsed or the events span more than one cycle. **Reproduce any warning it prints verbatim** — a tidy table over collapsed ids or several runs is worse than no table. For **Gate wait**, run `python3 .claude/skills/cycle/gate-report.py` (or the `~/` path) and paste its output. It reports how long the cycle spent waiting on a human and on which gates — the run report is otherwise blind to the largest non-agent cost in a cycle, and the one number that decides how many cycles a person can actually run at once. A fan-out clone should also be read across the whole run with `--log <clones-root>/gate-log.tsv`. Intervals that ended on an agent-completion wakeup are excluded from the gate figures and reported separately — they are idle-on-an-agent, not human wait, and mixing them overstated gate wait 40× in one run. If it says **not captured**, say that rather than writing zero: no log means the hooks are not wired, which is a different claim from nobody having waited. An `OPEN gate` line means this cycle is still parked at one — reproduce it. **Permission prompts** (probe 12) is required. The *wait* is now captured automatically — `gate-report.py` logs each ask as `gate=permission` and reports it apart from gate wait, because a dialog blocks the cycle without being a decision the pipeline asked for. Paste those lines; an `OPEN permission ask` means the cycle is blocked on one right now, so reproduce it rather than reporting the run as idle. **Refused calls are captured too, and they are a different thing.** A refusal opens no dialog and nobody waits, so it never appeared in any wait figure — fan-out 7 reported zero permission wait while three tool calls had been refused across two clones, because `PostToolUse` does not fire on a refusal. `gate-report.py` now reports them apart, with the reason and the agent. Reproduce that block: **a refusal an agent worked around is still a capability this pipeline does not have**, and the fix differs by reason — a classifier refusal on a sanctioned script wants a grant or a scoped script, a user rejection wants nothing. The rest is still yours and lives only in this session: name the agent, the exact command, and whether a grant or a scoped script is the right fix. **Harness findings** is required too: work the probe checklist in the `harness-findings` skill and fill the run report's `## Harness findings` section. These are process faults — what the harness cost this cycle — and are recorded independently of whether the work shipped, because a cycle can pass every product metric and still have built against the wrong base. Write `None — probes 1-12 checked, all clean.` only if you actually worked the list. If >10 reports exist, summarize oldest into `agent_tasks/agent_metrics.md` — and **delete the archived files only when `vault_root` is empty** (see report-template § Report archival; a vault is a permanent record, never pruned).
6. **Autonomous verify & review** — read `.omp/agent-config.md` Optional Agents section.

   **Mode override:** in `--mode hotfix`, **skip the review spawn entirely** and spawn only `verify` at **lite** depth (see 5.6.6). In `--mode lean` and `--mode full`, behave as below.

   **Skip flag:** when `skip_review_if_files_lt` (Per-phase skip flags in `.omp/agent-config.md`, default 0/off) is > 0 and `git diff [base] --name-only | wc -l` is below it, also skip review. Note the skip in the run report's Agent Audit (`review: skipped — files changed N < threshold M`).

   **Before spawning either, start the full-suite run.** Neither agent may launch one itself: at
   2m39s solo and ~8 minutes under fan-out contention it trips the 600s watchdog, which killed a
   `verify` agent (evidence-run2 F1). One run serves both — whether a commit's tests pass is a fact
   about that commit, not a judgment needing two opinions.

   With `ci_workflow` set in **Project Commands**:

   ```sh
   bash .claude/skills/cycle/publish-branch.sh ci [ci_workflow]
   ```

   **Issue it exactly as written — no `cd` prefix, no `&&` chain.** A compound command matches no
   prefix grant, so prefixing this with `cd <clone>` re-opens the permission dialog the script exists
   to close. Measured in fan-out 4: 18.5h of dialog wait across 6 asks, on commands the project had
   already granted, every one of them defeated by a leading `cd`. The script resolves the repository
   from its own working directory; you are already in it.

   It pushes the branch, dispatches the workflow **on that branch**, and prints the run id for this
   commit on stdout — nothing else goes to stdout, so capture it directly. It scopes the lookup by
   branch *and* head sha, because under fan-out several cycles dispatch within seconds of each other
   and an unscoped `--limit 1` hands one cycle another's run id; that misattribution is silent, and
   the agents would poll a real, green run for a commit they never audited.

   Pass that run id into **both** spawn prompts, **together with the suite result you already
   measured at step 1.** Both agents conclude on that result; the CI run is `ubuntu-latest`
   confirmation of it. An agent given a run id and no measured result has nothing to conclude on
   but the run, and in fan-out 6 one of them did not conclude at all — `verify` returned with
   `Verdict: IN PROGRESS` and "waiting for CI run to complete", while `review`, given the same id,
   cited the figures and finished. **If stdout is empty, treat it as a failed
   dispatch** — do not fall back to the newest run of the workflow.

   Do not dispatch by hand with `-f ref="$BR"`. `-f` passes a workflow *input*; it does not choose the
   ref the run is attributed to. Fan-out 4 dispatched that way three times and every run came back
   `headBranch: develop`, `headSha: <base>`, so the sha lookup found nothing and all three cycles fell
   back to a local suite run while believing they had a CI path.

   **When you need to block on a suite yourself, use `run-suite.sh wait <name>` — do not write a
   poll loop.** The subcommand exists for this and the skill never used to say so, which is how two
   orchestrators hand-rolled one and both got it wrong. In fan-out 6 one wrote
   `until ! run-suite.sh check <name>`, which exits immediately because `check` returns 3 while
   running, and reported a suite finished with ~70s left. In fan-out 7 another's background loop was
   killed by the harness for low memory with four sibling clones active — and a killed poller is
   indistinguishable from a killed suite until someone checks, so the reflex is to start a second
   full suite under memory pressure. `wait` blocks in one call, holds no lock of its own, and takes
   `--timeout`.

   Without `ci_workflow`, or when the dispatch failed, start **one** local run and pass its
   **name** to both agents:

   ```sh
   bash .claude/skills/cycle/run-suite.sh start phase4a-[feature-name] -- [Run all tests command]
   ```

   Read its verdict with `suite-result.py check phase4a-[feature-name]`
   (§ Reading a suite result) — one line, not a tail. **Pass that line to both
   agents verbatim**; it is the measured result they conclude on, and it is
   already the shape a report wants.

   The name matters. Both agents read that one run — they must never start their own, because two
   agents spawned in the same message would collide on one name, and `start` refuses a name that
   is already live rather than clobbering it. The name also carries the feature, so concurrent
   cycles on one machine do not collide either.

   If both are enabled, issue the two `Agent` calls in a **single message** so they run concurrently — verify and review must not gate each other.

   **They do not share state, but under a fan-out they share a checkout.** Neither is isolated in a
   clone, verify's Step 4c mutates `lib/` and restores it, and review's Step 6 fixes live in the
   working tree. Both sides are now guarded — review reads committed blobs at `$SHA`, and verify
   restores from what it read rather than resetting to HEAD — but the guard has a visible failure
   mode you own: **if verify's report contains a `restore-skipped:` line, the tree still holds a
   falsification mutation.** Verify saw the file change under it and correctly refused to clobber
   whatever was there. Do not commit, push or dispatch CI until you have read that file and put it
   right. Measured in fan-out 7: verify mutated two model files while review had a third modified,
   and they missed each other by luck.

   Run **Context Sources retrieval** for stages `verify` and `review` (see § Context Sources retrieval) and prepend any `## Context: <id>` blocks to the respective prompts below.

   **Compute verify depth (5.6.6).** Before spawning verify, gather the inputs from cycle state and the git diff:
   - `files_changed_count` = `git diff [base] --name-only | wc -l`
   - `test_files_touched` = any changed path matches the **Test path glob** (`.omp/agent-config.md` § Project Commands)
   - `domain_or_migration_files_touched` = any changed path under a domain/data layer (per `.omp/agent-config.md` § Layer Boundaries) or matches `**/migrations/**`
   - `deviations_non_empty` = cycle state `## Deviations` has entries
   - `phase3_retry_count` = count of `ESCALATION` lines (any level) in cycle state
   - `phase3_contradiction_exits` = count of `RESCUE contradiction-loop` entries in cycle state's `## Rescues`
   - `mid_cycle_scope_expansion` = cycle state `## Scope changes` has any `added` or `modified` entry

   Apply the rule:
   - **`--mode hotfix` forces `lite`** (overrides everything else).
   - **`deep`** when ANY of: `phase3_retry_count > 3` OR `phase3_contradiction_exits >= 1` OR `mid_cycle_scope_expansion`. Deep wins over lite if both conditions fire.
   - **`lite`** when ALL of: `files_changed_count < 3` AND NOT `test_files_touched` AND NOT `domain_or_migration_files_touched` AND NOT `deviations_non_empty`.
   - Otherwise **`standard`**.

   Record the chosen depth and its inputs in cycle state under `## References` → `Verify depth: <tier> | inputs: <key:value pairs>` for `self-improve` calibration.

   If `verify` is **enabled**: spawn the `verify` agent (not isolated — reads the main checkout):
   ```
   task(agent: "verify", context: "Audit AC coverage for the implemented feature.",
     tasks: [{ id: "verify", role: "AC auditor",
       assignment: "Source files: [paths]. Test files: [paths]. Branch: [branch-name]. Depth: <lite|standard|deep>. Read local://ac.md for AC. Read local://prd.md for PRD context. Report path: agent_tasks/reports/verify-[prd-stem]-[date].md — write your report there. Work autonomously." }])
   ```

   If `review` is **enabled**: spawn the `review` agent (not isolated — reads the main checkout):
   ```
   task(agent: "review", context: "Review code quality and architecture adherence.",
     tasks: [{ id: "review", role: "Code reviewer",
       assignment: "Branch: [branch-name]. Read local://prd.md for PRD context. Report path: agent_tasks/reports/review-[feature]-[date].md — write your report there. Work autonomously." }])
   ```

   Verify and review can be spawned as a single batch call (two items, minimal `context`) since they run concurrently. Each reads `local://` files on demand.

   Wait for both to complete.

   **Files-changed check** — `review` no longer applies its own fixes; it reports them under
   `## Proposed fixes` and writes nothing to `lib/`. So `## Files changed: None` is the expected
   result, and **writes there are now a finding**: either the agent definition drifted or something
   else touched the tree. Diff the tree against that section before acting on any verify finding —
   a verify finding that looks already-fixed used to be review's edit rather than a false positive,
   and attributing those edits to verify corrupts the run report.

   **Apply review's proposed fixes yourself, after both agents have returned** — never while verify
   is still running, because its Step 4c has `lib/` mutated in place and a write into that window
   makes verify decline to restore. Spawn one `coding` agent with the `## Proposed fixes` block as
   its assignment, let it commit, then re-run the suite. Budget for it: in fan-out 7 this was one
   spawn, 9 tool calls and 32s for a 13-line fix, and it happened anyway — it was simply unplanned,
   because review had applied the edit and nothing owned committing it.

   **Report-file check** — for each agent spawned, confirm its report file exists at the dictated path and its header `Verdict:` is no longer `IN PROGRESS`. A missing file or a still-`IN PROGRESS` verdict means the agent stalled before finishing — run **Stall salvage** (§3.4); its `PARTIAL — agent stalled` report then feeds the gate below.

   Include verify and review summaries in the cycle report (step 3). Then apply this gate before allowing 4B:

   | Verify verdict | NO IMPL count | 4B gate |
   |---|---|---|
   | PASS | 0 | Proceed to 4B automatically |
   | PARTIAL | 0 | Proceed — but present gaps and ask user to confirm before 4B |
   | PARTIAL | > 0 | Block 4B — present unimplemented criteria, require user to fix or explicitly accept the gaps |
   | FAIL | any | Block 4B — present failures, require fixes before release |

   Whenever that table stops and asks — a PARTIAL confirmation, or a blocked 4B — end the message with `<!-- gate:gate-4b -->` (§ Tagging a gate). The same applies when 4B leaves the PR with you and waits for it to be merged: tag that `<!-- gate:pr-merge -->`. Measured in fan-out 4, the merge wait was the single largest gate in the run — three clones, 48m29s — and every one of them was logged unlabelled.

   If `verify` was skipped, the gate does not apply — proceed to 4B but note: **"Verify was skipped — run `/verify` before merging."**

   If either agent is set to `skip` in config, do not spawn it. Instead recommend: **"Run `/verify` and/or `/review` in separate conversations, then return here for release."**

6z. **Now fill the run report's measurement sections** — **Agent Telemetry**, **Gate wait** and
   **Permission prompts**, all deferred from step 5. This is the first point at which `verify` and
   `review` appear in the event log at all; running the aggregator at step 5, as the numbering
   invites, produces a table that omits them every time.

7. Run the **Finalize one-shot spawn** (§ State persistence) with `FINALIZE report:[path]` — it archives, then deletes the state file. **Do not skip.** The cycle may end here if the user handles the PR manually.

7b. **Vault sync** — if `vault_root` (§ Docs Vault in `.omp/agent-config.md`) is non-empty, commit and push the vault repo so this cycle's reports reach its remote (e.g. `myapp-docs`). Orchestrator-run — the finalize monitor holds only the agent_states cleanup permission, not git. **Best-effort: a vault push failure must not fail the cycle.**

   ```sh
   # Stage only THIS CYCLE's files. Two things this must survive, both measured:
   #
   #   * The session shell is zsh, where an unmatched glob is a FATAL error rather
   #     than a literal — a lean cycle has no PRD and no PR body at this point, so a
   #     glob loop died on its second pattern and staged nothing while reporting
   #     success (evidence-run2 F2). So: no globs. `git status` does the enumerating,
   #     and its output is the same in every shell.
   #   * The vault is one repo shared by every clone, so an app-scoped add stages the
   #     other cycles' in-flight files too (evidence-run1 E13).
   #
   # The feature must be followed by a real delimiter — a date, `.`, `/`, or end of
   # line — or `auth` also matches `auth-refactor`.
   # Both flags are load-bearing, for different reasons, and both were verified
   # against real git rather than reasoned about:
   #
   #   -z            : without it git C-quotes any path containing a space or a byte
   #                   >= 0x80 — `"feat with space.md"`, `"caf\303\251.md"` — and the
   #                   quotes reach `git add`, which then matches nothing. It also
   #                   drops the `old -> new` arrow the non-z format uses.
   #   --no-renames  : with -z a rename is still ONE record carrying TWO fields,
   #                   `R  new\0old\0`. After `tr` that second field is a bare path
   #                   with no status prefix, and `cut -c4-` chops three characters
   #                   off the front of it. --no-renames emits two ordinary records
   #                   instead.
   #
   # Each failure drops an artifact from the commit with nothing noticing, which is
   # why the enumerated-vs-staged check below exists as well.
   FILES=$(git -C "{vault_root}" status --porcelain --no-renames -z --untracked-files=all \
     | tr '\0' '\n' \
     | cut -c4- \
     | grep -E "{feature}(-[0-9][0-9][0-9][0-9]-|[./]|$)" || true)

   if [ -n "$FILES" ]; then
     printf '%s\n' "$FILES" | while IFS= read -r f; do
       [ -n "$f" ] && git -C "{vault_root}" add -- "$f"
     done
   fi

   # Did everything we enumerated actually stage? `git add` can fail per path — a
   # name containing a newline survives `-z` but not the `tr` back to lines, a
   # pre-staged rename arrives as one `old -> new` record, and there will be shapes
   # nobody has listed yet. Each of those drops an artifact silently, which is the
   # failure mode this whole step keeps rediscovering. So compare, and say so.
   if [ -n "$FILES" ]; then
     MISSING=$(printf '%s\n' "$FILES" | while IFS= read -r f; do
       [ -n "$f" ] || continue
       # --no-renames here too: with rename detection on, a staged rename lists only
       # the new path, so the old one would look dropped when it is not.
       git -C "{vault_root}" diff --cached --no-renames --name-only -- "$f" | grep -q . \
         || printf '%s\n' "$f"
     done)
     if [ -n "$MISSING" ]; then
       echo "vault: WARNING — enumerated but not staged, these will NOT be committed:"
       printf '         %s\n' "$MISSING"
     fi
   fi

   # Then verify the index rather than trusting it. This is a safety net twice over:
   # it drops anything the enumeration over-matched, and it drops anything ANOTHER
   # concurrent cycle staged in the shared index between our add and our commit.
   git -C "{vault_root}" diff --cached --name-only \
     | grep -Ev -- "{feature}(-[0-9][0-9][0-9][0-9]-|[./]|$)" \
     | while IFS= read -r f; do git -C "{vault_root}" restore --staged -- "$f"; done

   # Refuse rather than commit foreign work. Every git call above can fail on
   # `.git/index.lock` when a sibling cycle is mid-write, and an unnoticed failure
   # of the `restore --staged` above leaves another cycle's file staged — which
   # would ride into this commit and recreate the commingling this design exists to
   # prevent (E13). So check the index one last time and refuse if it is not clean.
   # A refusal is recoverable; a quietly wrong commit in a shared permanent record
   # is not.
   # Retry the unstage before giving up: the reason a foreign path is still here is
   # usually that `restore --staged` lost the index lock to a sibling cycle, and
   # that is transient.
   for i in 1 2 3; do
     FOREIGN=$(git -C "{vault_root}" diff --cached --name-only \
       | grep -Ev -- "{feature}(-[0-9][0-9][0-9][0-9]-|[./]|$)" || true)
     [ -z "$FOREIGN" ] && break
     printf '%s\n' "$FOREIGN" | while IFS= read -r f; do
       [ -n "$f" ] && git -C "{vault_root}" restore --staged -- "$f"
     done
     sleep $((i * 2))
   done

   if [ -n "$FOREIGN" ]; then
     # Quoted: an unquoted $FOREIGN word-splits, so a path containing a space is
     # reported as several paths — and naming the blocking file is the entire point.
     echo "vault: REFUSING to commit — foreign paths still staged after 3 attempts."
     echo "       Nothing was committed. This cycle's artifacts remain STAGED and will"
     echo "       be unstaged by the next cycle's sync, so they are lost unless you act."
     echo "       Recover: cd {vault_root} && git status, unstage the foreign paths, then"
     echo "       commit this cycle's own files by hand."
     printf '         %s\n' "$FOREIGN"
     echo "RECORD THIS IN THE RUN REPORT'S HARNESS FINDINGS — nothing else logs it."
   elif ! git -C "{vault_root}" diff --cached --quiet; then
     # Retry the commit itself: losing the index lock is transient under fan-out.
     committed=0
     for i in 1 2 3; do
       git -C "{vault_root}" commit -m "cycle {feature}: reports ({app_slug})" && { committed=1; break; }
       sleep $((i * 2))
     done
     [ "$committed" = 1 ] || echo "vault: commit failed after 3 attempts — artifacts remain staged."
   fi

   # Concurrent cycles race on the push. Rebase and retry with backoff rather than
   # losing the race outright. The flag is load-bearing: a bare `done || echo` never
   # fires, because a loop's exit status is its last command's (the sleep), not the
   # failure's — which would swallow the report this step exists to produce.
   ok=0
   for i in 1 2 3 4 5; do
     if git -C "{vault_root}" pull --rebase --autostash && git -C "{vault_root}" push; then
       ok=1; break
     fi
     sleep $((i * 3))
   done
   [ "$ok" = 1 ] || echo "vault push failed after 5 attempts — reports are committed locally in the vault; push manually."
   ```

   **Why cycle-scoped, not app-scoped.** Fan-out 1 ran three cycles with an app-scoped add and
   commingled anyway, because all three shared `app_slug: myapp`: `22e1da8` says *cycle 378* and
   contains 404's and 419's PRDs; `842e27f` says *cycle 404* and contains 419's analyzer baseline;
   `793ddac` says *cycle 419* and contains **404's PR body**. Cleanly named, not cleanly scoped.
   App scoping isolates *applications* from each other, which is not the failure mode fan-out has.

   **Why scoped rather than `add -A`.** The vault is one repo shared by every clone and every
   application (§ Docs Vault). `add -A` stages whatever else happens to be in the working tree —
   under fan-out that is another cycle's in-progress report, committed under this cycle's message
   and possibly mid-write. Staging only `{app_slug}`'s three paths keeps a cycle's commit to its own
   artifacts. Paths are tested before staging because a lean cycle writes no PRD, and `git add` on a
   missing pathspec fails the whole step.

   **Why the retry.** Two cycles finishing close together both push; one is rejected non-fast-forward.
   The rebase-and-retry turns a lost race into a delay. `--autostash` covers another cycle's
   unstaged files being present during the rebase — it is not a lock, and a cycle writing *during*
   the rebase window can still conflict. Acceptable: the loop is bounded, the failure is reported,
   and the reports remain committed locally either way.

   **Still best-effort.** A vault failure must never fail the cycle. Report it and continue.

   If `vault_root` is empty, skip — reports are committed to the app repo as usual (backward-compatible default).

**4A is not complete until steps 1–7 are done (plus 7b where a vault is configured). Do not skip any step.** 4B is not complete until 8, 8b and 9 are done.

### 4B — Release (after gate passes; user confirmation required for PARTIAL)

8. **Push branch and open the PR.** Write the PR body per the `pr-body-format` skill to
   `cycle_reports/pr-body-[feature-name]-[YYYY-MM-DD].md`, then create the PR targeting the `pr_target`
   from `.omp/agent-config.md`:

   ```sh
   gh pr create --base [pr_target] --title "[type]([scope]): [summary]" \
     --body-file cycle_reports/pr-body-[feature-name]-[YYYY-MM-DD].md
   ```

   Always `--body-file`, never inline `--body` — the body contains tables and `<details>`
   tags. The skill owns the section order, the source map, and the honesty rules for gaps;
   do not improvise a body or paste the run report into it. If `pr_body_gate` (§ Cycle
   Options) is `true`, show the file and wait for the user before creating the PR.
8b. **Vault sync again** — if `vault_root` is non-empty, re-run **step 7b's sync verbatim**.

   The PR body is written *here*, in step 8, after 7b has already run. So a cycle never commits
   its own PR body: in fan-out 1 two were swept up by a *later* cycle's commit, and the last
   cycle's was simply orphaned, sitting untracked in the vault until someone noticed. This step
   is what makes a cycle's final artifact reach the vault under the cycle that produced it.

   Same best-effort contract as 7b — a push failure must not fail the release.

9. **Do not close a shipped story here, and do not set it Done.** Both happen on merge,
   and this step runs immediately after `gh pr create` — before it.

   The PR body's `Closes #<n>` is what closes the issue, and GitHub honours it when the PR
   merges. The board follows from the same event via the `pr-merged-board-done` workflow.
   A cycle stopped and asked about this rather than guessing (M31): step 9 used to close
   the issue and mark it Done at Finalize, so an issue read `completed` while its fix was
   unmerged — and stayed wrong if the PR was abandoned.

   So confirm the link exists rather than recording an outcome:

   ```sh
   gh pr view <pr> --json closingIssuesReferences -q '.closingIssuesReferences[].number'
   ```

   Empty, for a cycle that originated from a story, means the PR body lost its `Closes`
   line — fix the body. That is the whole of step 9 for a story that shipped.

   **A story that stopped existing rather than shipping is different**, and is still closed
   here, because no merge is coming:

   ```sh
   gh issue close <n> --reason "not planned" --add-label "superseded:<kind>"
   ```

   Do not mark it Done — it did not ship. Do not hand-edit `epic:` labels; they are
   generated from the sub-issue tree.

   If `gh` fails, stop and report. Never record the outcome in a local file instead.
10. **Write one changelog fragment** — a new file at `[Changelog fragments]/[feature-name].md`
    (**Artifact Paths** in `.omp/agent-config.md`; default `documentation/changelog.d/`). One
    cycle, one new file. **Never append to an assembled `CHANGELOG.md`** — it is the historical
    record and nothing in the pipeline rewrites it.

    ```markdown
    ---
    kind: added | changed | fixed | removed
    issue: [n]
    date: [YYYY-MM-DD]
    ---

    - **[One-line summary] ([#n](issue-url)).** [Why it changed and what shape it took.]
      - [Sub-points for constraints or scope decisions worth keeping.]
    ```

    A file per cycle rather than a shared file because a shared changelog has exactly one
    insertion point — the top of `## [Unreleased]` — and every cycle writes to it, so any two
    cycles running at once conflict by construction. Under a fan-out that is not a risk, it is a
    certainty. Two cycles never share a fragment filename, so there is nothing to merge.

    **Condense, do not restate.** The PR body already carries the full argument, so the fragment
    is the short version someone greps for months later — not a fourth copy. Measured in fan-out
    4: the `#430` changelog entry reproduced its PR body nearly sentence for sentence.

    If the project has no `Changelog fragments` path configured, skip this step and say so in the
    run report rather than inventing a location.

11. **In a fan-out clone, finish the clone.** Last thing in the cycle, after the fragment is
    committed:

    ```sh
    bash .claude/skills/cycle/reap-clones.sh finish --apply
    ```

    It deletes the clone's regenerable build output and marks the clone reapable. It refuses on
    its own outside a fan-out clone, so run it unconditionally rather than detecting the clone
    yourself. It does **not** remove the clone — a cycle cannot delete the worktree its own
    session is standing in; removal is `sweep`, which you do not run.

    **This is step 11 and not part of Finalize, deliberately.** It marks the clone's HEAD, and
    Finalize is not the last thing a cycle does — step 10 commits after it. Measured in fan-out 5
    (J3): the marker recorded a commit the cycle then moved past, `sweep` refused the clone, and
    two sibling clones that happened to commit their fragment before Finalize did not hit it.
    Same skill, same mode, two orderings.

