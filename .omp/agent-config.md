# Agent Pipeline Configuration

This file is the central configuration for the agent-sdlc pipeline. Agents and skills read specific sections at runtime. Edit this file directly to customize behavior — or run `/setup` to generate it interactively.

---

## Active Pack

The language/framework pack this project uses. A pack supplies the conventions, test
patterns, anti-patterns, and code idioms for one stack (`.claude/packs/<pack>/`). This field
is informational + used by `/setup`; the *active* conventions are loaded deterministically
from the `project-conventions` skill (see `.claude/packs/README.md` for the swap procedure).

| Field | Value |
|---|---|
| active_pack | `flutter` |

Available packs: `flutter` (default), `dotnet` (alternate template). Author a new one by
copying `.claude/packs/dotnet/` — see `.claude/packs/README.md`.

---

## Artifact Paths

Every artifact is one of four classes:
- **local** — committed to the application repo; travels with the feature branch.
- **runtime** — never committed; covered by the managed `.gitignore` block (cycle state, task files, telemetry; Claude-Code worktrees).
- **vault** — written to the external docs vault when `vault_root` is set (see **Docs Vault** below); otherwise treated as local.
- **remote** — lives in GitHub, not on disk. Reached with live `gh` calls, never mirrored
  locally. If `gh` fails, stop and report — there is no file fallback.

`remote` paths use a scheme prefix rather than a filesystem path:
`issues:label=<label>` for an issue query, `project:<owner>/<number>` for a Projects v2 board.
All of them resolve against `tracker_repo`.

| Key | Value |
|---|---|
| `tracker_repo` | *(blank — auto-resolves)* |

**Leave `tracker_repo` blank.** The git remote already holds the repo slug; writing it here
too is a second home for the same fact. Resolve it at use time instead:

```sh
gh repo view --json nameWithOwner -q .nameWithOwner
```

Set it explicitly in exactly two cases:
- Trackers live in a **different repo** than the code.
- The repo has **multiple remotes** and `gh` picks the wrong one — its heuristic can prefer
  `upstream` over `origin`, which matters in a fork. Check with the command above before
  assuming; if it prints what you expect, leave the key blank.

If it is blank and the resolve command fails, **stop and report** — do not guess a slug.

| Artifact | Path | Class |
|---|---|---|
| PRDs | `agent_tasks/prds/prd-*.md` | vault |
| Task files | `agent_tasks/tasks-*.md` | runtime |
| Cycle state | `agent_states/` | runtime |
| Telemetry event logs | `agent_states/events/` | runtime |
| Phase-3 worktrees (Claude Code only) | `.claude/worktrees/` | runtime |
| Cycle reports | `cycle_reports/` | vault |
| Run + verify + review reports | `agent_tasks/reports/` | vault |
| Customer profiles | `product/customer-profiles.md` | vault |
| Documentation | `documentation/` | local |
| Product description | `documentation/FEATURES.md` | local |
| Changelog fragments | `documentation/changelog.d/` | local |
| Changelog (assembled, optional) | `documentation/CHANGELOG.md` | local |
| Stories | `issues:label=story` | remote |
| Bugs | `issues:label=bug` | remote |
| Feature backlog | `issues:label=feature` | remote |
| Roadmap | `project:<owner>/<number>` | remote |

`FEATURES.md` is product description, not a tracker — it stays local and hand-owned.
The feature *backlog* is `label:feature` issues.

**Customer profiles are hand-owned input, not a generated artifact** — the one vault-class path
that is. They are vault-class because they outlive any single application: the archetypes a
product serves are the same across the apps that share a vault, and `/refine` reads them rather
than writing them. With `vault_root` empty they stay local, like every other vault path.

**The changelog is a directory, not a file.** One fragment per cycle, named for the cycle's
feature. A single changelog file has one insertion point — the top of `## [Unreleased]` — and
every cycle writes to it, so any two cycles running at once conflict by construction. Measured
in myapp: 95 of 878 commits over 60 days touched `CHANGELOG.md`, and it is the most frequent
source of merge conflicts in the repository. Fragments cannot collide, because two cycles never
share a filename.

Set **Changelog (assembled)** only if the project wants a single narrative file; a project that
reads its changelog as developer history can leave the fragments as the changelog and never
assemble them. Either way an existing `CHANGELOG.md` stays exactly where it is — it is the
historical record, and nothing rewrites it.

---

## Docs Vault (external artifact store)

When `vault_root` is set, the orchestrator redirects **vault**-class artifacts out of the application repo into a shared, git-backed **vault repo** (e.g. `myapp-docs`) and commits + pushes it at cycle Finalize (§ cycle SKILL, Phase 4A step 7b). This keeps retrospective process artifacts (cycle reports, run/verify/review reports) out of the product's git history while versioning them in one place, browsable as plain Markdown across every application that shares the vault. Leave `vault_root` empty to keep these artifacts local (committed to the app repo) — the framework is fully backward-compatible.

| Field | Value | Description |
|---|---|---|
| vault_root |  | Absolute path to the vault root. Empty = disabled. Example: `/Users/you/Documents/myapp-docs` |
| app_slug |  | Per-application subdirectory inside the vault. Empty = derived from the repo directory name. |

**Resolution.** With `vault_root` set, the orchestrator ensures these symlinks exist at startup (creating the vault targets if missing, migrating any pre-existing local reports into them first) so every relative artifact path resolves into the vault with no per-reference changes:

| Repo path (becomes a symlink) | → Vault target |
|---|---|
| `cycle_reports` | `{vault_root}/cycle_reports/{app_slug}/` |
| `agent_tasks/reports` | `{vault_root}/reports/{app_slug}/` |
| `product` | `{vault_root}/product/{app_slug}/` |

The symlinks are added to the managed `.gitignore` block (no trailing slash — git treats a symlink as a file), so the application repo never commits vault artifacts. The vault is a standalone git repo with its own remote (e.g. `myapp-docs`), independent of any application repo; the orchestrator commits and pushes it at cycle Finalize so reports reach the remote without manual steps.

---

## Model Allocation

Active preset: **personal**

| Agent | personal | team | enterprise | open-weight | local-70b | maas |
|---|---|---|---|---|---|---|
| create-prd | sonnet | sonnet | opus | openrouter/deepseek/deepseek-v4.1-flash | openrouter/openai/gpt-oss-20b | openrouter/google/gemma-4-31b-it |
| generate-tasks | sonnet | sonnet | opus | openrouter/deepseek/deepseek-v4.1-flash | openrouter/openai/gpt-oss-20b | openrouter/google/gemma-4-31b-it |
| scaffold | sonnet | sonnet | sonnet | openrouter/deepseek/deepseek-v4.1-flash | openrouter/openai/gpt-oss-20b | openrouter/google/gemma-4-31b-it |
| ui-story | sonnet | sonnet | sonnet | openrouter/deepseek/deepseek-v4.1-flash | openrouter/openai/gpt-oss-20b | openrouter/google/gemma-4-31b-it |
| coding | sonnet | sonnet | sonnet | openrouter/deepseek/deepseek-v4.1-flash | openrouter/openai/gpt-oss-20b | openrouter/google/gemma-4-31b-it |
| test | sonnet | sonnet | sonnet | openrouter/qwen/qwen3.8-flash | openrouter/openai/gpt-oss-20b | openrouter/google/gemma-4-31b-it |
| verify | sonnet | sonnet | opus | openrouter/qwen/qwen3.8-flash | openrouter/openai/gpt-oss-20b | openrouter/google/gemma-4-31b-it |
| review | sonnet | sonnet | opus | openrouter/qwen/qwen3.8-flash | openrouter/openai/gpt-oss-20b | openrouter/deepseek/deepseek-v4.1-flash |
| adversarial-tester | haiku | haiku | sonnet | openrouter/openai/gpt-oss-20b | openrouter/openai/gpt-oss-20b | openrouter/google/gemma-4-31b-it |
| self-improve | sonnet | sonnet | opus | openrouter/deepseek/deepseek-v4.1-flash | openrouter/openai/gpt-oss-20b | openrouter/google/gemma-4-31b-it |
| monitor | haiku | haiku | haiku | openrouter/openai/gpt-oss-20b | openrouter/openai/gpt-oss-20b | openrouter/google/gemma-4-31b-it |
| pre-digest | haiku | haiku | haiku | openrouter/openai/gpt-oss-20b | openrouter/openai/gpt-oss-20b | openrouter/google/gemma-4-31b-it |
| salvage | haiku | haiku | haiku | openrouter/openai/gpt-oss-20b | openrouter/openai/gpt-oss-20b | openrouter/google/gemma-4-31b-it |
| test-preflight | sonnet | sonnet | sonnet | openrouter/openai/gpt-oss-20b | openrouter/openai/gpt-oss-20b | openrouter/google/gemma-4-31b-it |
| supervisor | haiku | haiku | haiku | openrouter/openai/gpt-oss-20b | openrouter/openai/gpt-oss-20b | openrouter/google/gemma-4-31b-it |
| orchestrator (/cycle) | opus | opus | opus | openrouter/qwen/qwen3.8-2.4t-a95b | openrouter/openai/gpt-oss-20b | openrouter/deepseek/deepseek-v4.1-flash |

**A cell may hold either a tier label or a concrete provider id.** The label form
(`sonnet`) resolves through § Model Versions; the concrete form passes straight through. The
`open-weight` preset uses concrete ids because a tier label cannot express "this agent needs a
1M window and that one does not" — which is the whole point of the column.

**`local-70b` is a target and is expected to fail.** Every cell is `gpt-oss-20b`, the only
model at or under 70B that has cleared a probe. `model_allocation.py --column local-70b` names
the four roles over its 131k window; twelve of sixteen already fit, blocked by context rather
than capability. Pinned by `tests/test_local_70b_gap.py`; rationale in that file's docstring.

**`maas` is the preset that is meant to run.** `local-70b` is a self-hosting target and is
expected to fail; `open-weight` rents frontier-scale models. `maas` is the 2026 decision
recorded in [engineering-meta](https://github.com/dsh-a/engineering-meta), split by the only
thing that differs between roles — context window. `deepseek-v4.1-flash` (1,048,576) takes
`orchestrator` and `review`, the two over 262k; `gemma-4-31b-it` (262,144, and the only model
measuring 100/100/100 on review/test-preflight/verify) takes the other fourteen. **~$60/month**
against 912 requests/day at 123k input tokens each, 97.4% of it a cacheable prefix.

A `qwen3-coder` judgement tier was rejected — same window, 77% vs 100% on verify, 3.3× the
price. What this preset is honest about: **the orchestrator has never been probed** — `tests/probes/`
covers `review`, `test-preflight` and `verify` only. `deepseek-v4.1-flash` is chosen for window
and price; its family scored **0% on verify**, so it must not spread beyond these two roles (it
scored 100% on `review`, one of them). Twelve of the fourteen bulk roles are equally unprobed.
And **every p90 here is a Claude-tokenizer count**, ~32% high against these models' own
tokenizers — rescaled, orchestrator is ~255k and review ~194k, both inside 262,144, which would
collapse this to one tier. That rescale is an estimate, not a measured run.

**Concrete ids are omp-only.** Claude Code's `Agent` tool takes a fixed tier enum — the four
labels listed in § Model Versions — and rejects a provider id, so under Claude Code the
orchestrator reads the `personal` column regardless of which preset is active, and says so in
its run report. This is a harness limit, not a preference.

**Sizing is against measured peaks, not price.** Every id above is chosen so its context
window clears that agent's p90 in `docs/internal/agent-requirement-profiles.md`. The obvious
cheap choice fails this: `gpt-oss-20b` won the qualification matrix outright but holds 131k,
where `verify` peaks at 251k and `review` at 286k — so it takes the small-context rows only.
`tests/model_allocation.py` enforces this against § Model Provenance, and would have caught
that assignment automatically.

To override a single agent regardless of preset, change the value in that agent's row under the active preset column. The cycle orchestrator reads this table for all agent spawns — implementation agents at Phase 3.3, pre-digest and monitor at Phase 3 start.

> **Model resolution under omp:** each agent runs on the model the orchestrator passes at spawn; where it passes none (the Phase-4A `verify`/`review` spawns), the agent falls back to the tier in its `.omp/agents/*` frontmatter. So changing the preset re-tiers the table-driven spawns (generic `task` subagents, `monitor`, `pre-digest`, `supervisor`) but not the Phase-4A named agents — edit their `.omp/agents/*` frontmatter for those. Under Claude Code the orchestrator passes `model:` on every spawn, so the table governs all.

### Model Provenance — **framework only**

**Not project config.** This is the framework's own record of which open-weight models it has
qualified, read by `tests/vram_footprint.py` and `tests/test_local_70b_gap.py`. No skill or
agent reads it at runtime and it is not in `REQUIRED_CONFIG_SECTIONS`, so a deployment does not
carry it — `deploy.sh check` skips any section marked **framework only**.

Every concrete id in § Model Allocation, plus **candidates under evaluation** (marked in
`Mirrored`), with what it would take to run each without a provider. Context is verified
against the live catalogue; params in `total / active` form come from the vendor's naming
convention, not a measurement. **`KV/token` is `unknown` wherever nobody has read it off a
model card** — `tests/vram_footprint.py` refuses to price those rows rather than estimating,
and the catalogue does not expose it. The scenario this framework plans for assumes premium APIs become unaffordable, and
open weights are only open **while you hold the file** — so a model that passes qualification
should be mirrored, and a mirror is worth nothing without the revision it was qualified at.

| Provider id | Weights | Params (total / active) | Context | KV/token | Mirrored |
|---|---|---|---|---|---|---|
| `openrouter/qwen/qwen3.8-2.4t-a95b` | Qwen/Qwen3.8-2.4T-A95B | 2.4T / ~95B | 1,048,576 | GQA — see engineering-meta hardware/server-requirements.md | **no — not self-hostable** |
| `openrouter/qwen/qwen3.8-flash` | Qwen/Qwen3.8-Flash | — | 1,000,000 | GQA | no |
| `openrouter/qwen/qwen3.8-27b` | Qwen/Qwen3.8-27B | 27B dense | 262,144 ⚠ | 64 KB | no |
| `openrouter/deepseek/deepseek-v4.1-flash` | deepseek-ai/DeepSeek-V4-Pro | — | 1,048,576 | 890 B | no |
| `openrouter/openai/gpt-oss-20b` | openai/gpt-oss-20b | 20B | 131,072 | 24 KB | no |
| `openrouter/qwen/qwen3-next-80b-a3b-instruct` | Qwen/Qwen3-Next-80B-A3B-Instruct | 80B / 3B | 262,144 | 24 KB | no — candidate |
| `openrouter/qwen/qwen3-coder-30b-a3b-instruct` | Qwen/Qwen3-Coder-30B-A3B-Instruct | 30B / 3B | 262,144 | 96 KB | no — candidate |
| `openrouter/openai/gpt-oss-120b` | openai/gpt-oss-120b | 120B | 131,072 | 36 KB | no — candidate |
| `openrouter/google/gemma-4-31b-it` | google/gemma-4-31b-it | 31B dense | 262,144 | 192 KB | no — **maas bulk tier** |

**KV/token is measured**, read from each model's `config.json` on 2026-09-25. Derivations, and a disputed context window for `qwen3.8-27b`, are in [`hardware/server-requirements.md`](https://github.com/dsh-a/engineering-meta/blob/main/hardware/server-requirements.md) § Measured KV per token, in **engineering-meta**.

**Fill `Mirrored` with the revision hash actually downloaded, not `yes`.** A model updated
underneath you is the failure this column exists to make visible, and the qualification matrix
records the checkpoint each cell was measured at for the same reason.

**2.4T-A95B is a ceiling reference, not a deployment target.** Active params drive throughput,
total params drive VRAM, and 2.4T total is a multi-node deployment at any quantisation — it
cannot go on a rented box. It earns its place by being the same family, with the same prompt
conventions, as members that can: the 27B is two orders of magnitude smaller and shares them.
That is the property to select families on.

### Model Versions — **omp only**

Maps the allocation table's labels to omp's canonical tier ids. omp coalesces OpenRouter model ids
onto these (see `.omp/models.yml.sample` § modelAliases), so `modelRoles` in `.omp/config.yml`
resolves correctly whichever provider is actually serving the tier.

| Label | omp canonical id |
|---|---|
| opus | claude-opus-4-6 |
| sonnet | claude-sonnet-4-5 |
| haiku | claude-haiku-4-5 |

**Under Claude Code this table does not apply — pass the bare label.** The `Agent` tool's `model`
parameter takes a fixed tier enum (`opus`, `sonnet`, `haiku`, `fable`), not a version string, and
rejects a concrete id outright. The ids above are omp's own naming and mean nothing to it.

That split is the whole rule, and it is easy to get backwards:

| | Spawn passes |
|---|---|
| **omp** | the concrete id from this table |
| **Claude Code** | the label from § Model Allocation, verbatim |

Two consequences worth stating rather than rediscovering:

- **The orchestrator's own tier is not settable under Claude Code.** § Model Allocation lists
  `orchestrator (/cycle) | opus`, but a session's model is chosen when it starts. The row is a
  statement of intent that nothing enforces — check it yourself if it matters.
- **`fable` is reachable under Claude Code and absent from the allocation table.** Nothing is
  broken by that; it just means the table does not describe every tier the harness offers.

---

## Effort Allocation

> `verify` and `review` moved from `max` to `high` (2026-09-05). Both run at **sonnet** under the
> active preset — they are only `opus` under `enterprise` — so effort is the sole quality lever on
> them, and maxing it made Phase 4A the pipeline's heaviest moment. Under fan-out that moment is a
> spike: cycles started together finish together, so N cycles converge on 2N max-effort agents.
> Raise either back to `max` for a release audit, or when a cycle's blast radius warrants it.

| Agent | Effort |
|---|---|
| create-prd | high | openrouter/google/gemma-4-31b-it |
| generate-tasks | high | openrouter/google/gemma-4-31b-it |
| scaffold | medium | openrouter/google/gemma-4-31b-it |
| ui-story | high | openrouter/google/gemma-4-31b-it |
| coding | high | openrouter/google/gemma-4-31b-it |
| test | high | openrouter/google/gemma-4-31b-it |
| verify | high | openrouter/google/gemma-4-31b-it |
| review | high | openrouter/deepseek/deepseek-v4.1-flash |
| adversarial-tester | high | openrouter/google/gemma-4-31b-it |
| self-improve | high | openrouter/google/gemma-4-31b-it |
| monitor | low | openrouter/google/gemma-4-31b-it |
| test-preflight | low | openrouter/google/gemma-4-31b-it |
| supervisor | low | openrouter/google/gemma-4-31b-it |

---

## Optional Agents

Agents spawned during Phase 4A. Set to `skip` to disable.

| Agent | Status | Notes |
|---|---|---|
| verify | enabled | | openrouter/google/gemma-4-31b-it |
| review | enabled | | openrouter/deepseek/deepseek-v4.1-flash |
| supervisor | enabled | *(omp only — under Claude Code the supervisor is disabled regardless of this value; see `/cycle` § Cadence under Claude Code)* | openrouter/google/gemma-4-31b-it |

---

## Hygiene flags (§5.8)

Long-tail policy knobs. All default to conservative behavior.

### Analyzer baseline (5.8.1)

| Flag | Default | Behavior |
|---|---|---|
| `analyzer_baseline` | `soft_warn` | `off` — no baseline tracking. `soft_warn` — record analyzer warnings at Phase 3 start; Phase 4A surfaces any new warnings introduced during the cycle but does not block. `hard_fail_if_exceeded` — same recording, but new warnings flip review verdict to REQUEST CHANGES. |

Baseline is recorded into `agent_states/analyzer-baseline-<feature>.txt` at Phase 3 start by capturing the **Analyze / lint** command (§ Project Commands) output. Phase 4A re-runs and diffs. It lives in `agent_states/` because it is scratch for exactly one cycle — it used to be written into `cycle_reports/`, where nothing ever consumed or pruned it.

### Compact at phase boundaries (5.8.2)

| Flag | Default | Behavior |
|---|---|---|
| `auto_compact_at_boundaries` | `off` | When `on`, the orchestrator invokes `/compact` at Phase 2→3 and Phase 3→4A transitions to reclaim context. Off by default because compaction can cost orchestrator decision-continuity; enable once your cycles have telemetry showing the trade-off is favorable. |

### Known-pitfalls loop (5.8.3)

| Flag | Default | Behavior |
|---|---|---|
| `customer_profiles_path` | `product/customer-profiles.md` | Path to the project's customer-profile file, read by `/refine`'s `profile-impact` probe. Vault-class, so it resolves into the vault when `vault_root` is set. If the file is absent the probe reports `unavailable` rather than clean. Set to empty string to disable. |
| `known_pitfalls_path` | `documentation/known-pitfalls.md` | Path to the project's known-pitfalls file. If the file exists, the orchestrator pre-attaches matching entries to implementation-agent prompts (matched by file globs). Set to empty string to disable. |

See cycle SKILL § Known pitfalls for the file format.

### Bug-triage (5.8.4)

| Flag | Default | Behavior |
|---|---|---|
| `aggregate_bugs_into` | `<owner>/<repo>` | **Repo slug** the `self-improve` agent files new "Bugs discovered" entries into as GitHub issues (dedup by `gh issue list --search`). Was a file path before the tracker migration. Set to empty string to disable. |

---

## Per-phase skip flags (5.6.2)

Conservative defaults. Flags act as **additional** skip conditions on top of the active `--mode`. Set a flag to `0` or `false` to disable that specific skip.

| Flag | Default | Skips |
|---|---|---|
| `skip_predigest_if_files_lt` | 2 | Pre-digest spawn when the parent task's "Relevant Files" count is below this. (Codifies existing inline rule — small tasks don't need digestion.) |
| `skip_preflight_if_no_existing_tests` | true | `test-preflight` spawn when grep of the **Test path glob** (§ Project Commands) for the touched symbols returns no hits. (Codifies the greenfield short-circuit from 5.4.3.) |
| `skip_review_if_files_lt` | 0 | Review spawn when changed files below this threshold. `0` = always run review. |
| `skip_supervisor_if_total_subtasks_lt` | 3 | Supervisor spawn for the cycle when the task list is small enough that observation overhead exceeds value. |

After ≥ 20 cycles of telemetry, `self-improve` proposes new values based on observed correlations between skipping and downstream rework.

---

## Supervisor Thresholds

Item 5.5.4 placeholders. **All values are best guesses — `self-improve` tunes from real cycle telemetry once enough cycles have run.** Edit here to override.

| Key | Default | Meaning |
|---|---|---|
| `cadence_n` | 5 | Run a supervisor check after every N tool calls per agent |
| `window_k` | 20 | Read the last K events of an agent on each check |
| `stall_seconds` | 300 | An agent with no events for ≥ this duration triggers `stall` |
| `spiral_edits` | 3 | Same file edited this many times without an intervening Read → `spiral` |
| `spiral_errors` | 3 | This many consecutive `exit:error` events → `spiral` |

### Detector states

| Detector | Default | Notes |
|---|---|---|
| `spiral` | enabled | Repeat-edit / repeat-error pattern detection |
| `drift` | enabled | File touches outside the agent's parent-task scope |
| `stall` | enabled | Idle agent above the stall threshold |
| `shallow` | enabled | Edit/Write before any Read of that file |
| `contradiction` | enabled | Cycle-state RESCUE contradiction-loop newer than last check |

Set a detector to `disabled` to silence it without removing the supervisor entirely.

When enabled, these agents run autonomously during Phase 4A and their reports are included in the cycle report. When set to `skip`, the cycle recommends running them manually in separate conversations.

---

## Project Commands

Agents run these commands to test, lint, and generate code. This table is the **per-project override point** — the live values every implementation agent reads at runtime. The defaults below are seeded from the active pack (`flutter`; canonical list in `.claude/packs/flutter/commands.md`). Update them to match your project's toolchain.

| Purpose | Command |
|---|---|
| Run all tests | `flutter test` |
| Run specific test file | `flutter test <path>` |
| Run single test by name | `flutter test <path> --plain-name "<test name>"` |
| CI workflow (dispatchable) | `ci.yml` |
| Analyze / lint | `flutter analyze` |
| Format | `dart format .` |
| Code generation | `flutter pub run build_runner build --delete-conflicting-outputs` |
| Test path glob | `test/**` |
| Test anti-patterns | `.claude/packs/flutter/test-antipatterns.md` |

- **CI workflow** is the `workflow_dispatch`-enabled GitHub Actions workflow `verify` and `review` trigger for a full-suite result instead of running it locally. Leave blank if the project has none; agents then fall back to `run-suite.sh`. Requires the workflow to accept a `ref` input.
- **Run single test by name** is what forced falsification runs against. Scoping the run to one test is what makes the evidence checkable: a broad run can go red for an unrelated reason and be attributed to the wrong assertion, which is how a falsification that could not possibly reproduce was once reported as observed.
- The `Code generation` command is optional — remove it if your project has no code generation step.
- **Test path glob** is the path the silent-skip gate and preflight short-circuit scope to (default `test/**` for Flutter; .NET-style layouts use `tests/**`).
- **Test anti-patterns** points at the regex list the cycle silent-skip gate greps changed test files against. It defaults to the active pack's file; override per-project here.

---

## Architecture Review Rules

These sections are **project-specific overrides** layered on top of the active pack's `project-conventions` — the canonical source for the stack's layer boundaries, patterns, naming, line-length, logging, comments, and error-handling (see `.claude/packs/<active-pack>/conventions.md`). The `review` (Step 2) and `verify` agents read the pack for the stack's rules and consult these sections for any per-project overrides. **Leave a section empty to use the pack's rules unchanged.**

### Layer Boundaries

Fill this table only to **override or extend** the active pack's layer/import rules for this specific project. The review agent checks that files in each defined layer only import from allowed sources. Path patterns are project-specific — e.g. the `flutter` pack uses `lib/domain|data|ui/`, the `dotnet` template uses `src/**/Domain|Application|Infrastructure/`.

| Layer | Path pattern | Allowed imports | Forbidden imports |
|---|---|---|---|
| _(project override — leave empty to use the pack)_ | | | |

### Pattern Compliance

List only project-specific patterns that **override or extend** the pack's (state management, DI, view rules, interface usage at boundaries). Leave empty to use the pack unchanged. The review agent checks changed files against the pack's patterns plus anything added here.

- _(project override — e.g. "this app uses Riverpod instead of the pack's default DI")_

### Convention Checks

Add rows only to **override** the pack's conventions (naming, line-length, logging, comments, error-handling) for this project. Leave empty to use the pack's defaults.

| Convention | Rule (project override) |
|---|---|
| _(e.g. Line length)_ | _(e.g. `120` — overrides the pack's default)_ |

---

## Context Sources (MCP / RAG plug-in points)

External knowledge the pipeline consults at specific stages — a documentation MCP, a
codebase-analysis / RAG service, an ADR store, etc. The orchestrator reads this table and,
at each listed stage, queries the enabled sources **once** and writes the result to a `local://` file the
spawned agents read (the same downward-context mechanism used for known-pitfalls and the
pre-digest). See `.claude/skills/context-sources/SKILL.md` for the full contract and
`docs/CONTEXT-SOURCES.md` for setup. Connect the actual MCP servers in `.omp/mcp.json`
(template: `.omp/mcp.json.sample`).

| id | type | tool / skill | consult_at | required | enabled | query_hint |
|---|---|---|---|---|---|---|
| company-a-docs | mcp | `mcp__company-a-docs__search` | prd, tasks, implement, review | optional | `true` | feature name + domain keywords; engineering/product docs for the touched area |
| codebase-rag | mcp | `mcp__codebase-rag__query` | tasks, implement, verify | optional | `false` | relevant file paths + public symbols; similar prior implementations & constraints |

**Columns.**
- **type** — `mcp` (a connected MCP server; under omp the tool is auto-discovered from `.omp/mcp.json` — no `ToolSearch`) or `skill` (a local skill the orchestrator runs).
- **consult_at** — pipeline stages where this source is queried. Vocabulary: `prd`, `tasks`, `predigest`, `implement`, `review`, `verify`. (`predigest` is excluded for cost by default — the pre-digest is a cheap summarizer.)
- **required** — `optional`: unavailability degrades silently with a logged marker. `required`: unavailability surfaces a gate (and in autonomous mode logs `context-source <id>: DEGRADED` and proceeds). **Never mark an unreleased source `required`.**
- **enabled** — `false` rows are skipped cleanly (e.g. `codebase-rag` until it is released and wired).

---

## Cycle Options

| Option | Value | Description |
|---|---|---|
| auto_verify | `true` | Spawn verify agent during Phase 4A |
| auto_review | `true` | Spawn review agent during Phase 4A |
| feature_idea_on_empty | `true` | When /cycle has no args and no active state, offer open feature issues: `gh issue list --label feature --state open` |
| pr_body_gate | `true` | At Phase 4B step 8, show the generated `cycle_reports/pr-body-<feature>-<date>.md` and wait for confirmation before running `gh pr create`. Set `false` to open the PR without a pause. |
| agent_messaging | `false` | Whether the orchestrator delegates state persistence to a background monitor. `false` (default): the orchestrator writes cycle state inline and only spawns the monitor at Finalize. `true`: a background monitor receives state-update verbs via irc (`irc(op: "wait")`) and maintains the state file. Under omp, irc is always available to subagents, so `true` is viable. Leave `false` for the leanest orchestrator context. |


## Branch Configuration

These are **this repository's** values, not a template default — `/setup` writes them per project
from what the project actually uses. A project with only `main` sets both fields to `main`.

Work merges **feature → develop → main**. `develop` is the integration branch and the one a cycle
targets; `main` is release. Until 2026-09-12 this repo's PRs went straight to `main` and `develop`
sat 150 commits behind, which is why this section now says what the flow is rather than only which
branch to name.

| Field | Value |
|---|---|
| base_branch | develop |
| feature_branch_pattern | [kind]/[short-description] |
| pr_target | develop |

Agents and skills read `base_branch` when running git diffs and creating PRs. Update `pr_target` if your team's PR flow targets a different branch than `base_branch`.
