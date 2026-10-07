# `.claude/agents/` — the agent team

Each `*.md` file is a subagent: YAML frontmatter (name, model, `tools:`, `skills:`,
`produces:`) plus a system-prompt body. The orchestrator (`/cycle`) spawns these during the
pipeline; it writes no implementation code itself.

## Catalog

| Agent | Phase | Role |
|---|---|---|
| `create-prd` | 1A | Writes the PRD from a feature description |
| `generate-tasks` | 2 | Decomposes the PRD into a tagged task list |
| `pre-digest` | 3 | Summarizes the files a task will change, so the implementer reads one file instead of four |
| `scaffold` | 3 | Creates new components from pattern shapes + pack snippets |
| `ui-story` | 3 | Implements presentation-layer features + tests |
| `coding` | 3 | General code changes that are not a scaffold, a UI story, or a test |
| `test` | 3 | Writes rigorous, anti-faking tests |
| `test-preflight` | 3 | Classifies existing tests (keep / update / delete) before the test agent |
| `verify` | 4A | Independent AC-coverage audit |
| `plan-reviewer` | — | Read-only audit of a design plan against framework source and a real deployment. Not spawned by `/cycle`; invoke directly. |
| `review` | 4A | Independent code review |
| `adversarial-tester` | opt-in | Second-pass test hardening |
| `monitor` | 3–4 | Cycle-state persistence / finalize |
| `supervisor` | 3 | Observes event logs; emits whispers + escalations |
| `self-improve` | — | Applies pipeline improvements from run reports |

## How conventions reach an agent

Conventions are loaded **deterministically** via the `skills:` frontmatter — e.g. `ui-story`,
`test`, `review`, `scaffold` list `project-conventions`. That skill is the active stack's
conventions (populated from a pack). This is why there is no runtime "read a pointer, chase a
file" hop — the skill name in frontmatter resolves at spawn time.

## How external context reaches an agent

The orchestrator queries enabled **Context Sources** once per stage and **injects the result
text downward** into the spawned agent's prompt as a `## Context: <id>` block — the same
mechanism as the pre-digest and known-pitfalls. Agents do **not** call MCPs themselves (the
narrow agents have no MCP tools), and they echo `context-sources-consulted: <ids|none>` in
their handoff for auditability. See [`../skills/context-sources/SKILL.md`](../skills/context-sources/SKILL.md).

## Two per-agent things that are NOT config-driven

- **`tools:` frontmatter** — the Bash/MCP allowlist is static per agent. The default pack
  (`flutter`) uses `Bash(flutter …)` + `mcp__ide__getDiagnostics`. Switching toolchains means
  editing these tokens across the implementation/review agents.

  **The grants are a contract, not a preference.** A Phase-3 agent works in an isolated
  workspace and commits its own work, so `coding`, `test`, `scaffold` and `ui-story` must each
  be able to run `git log` (the mandated base check), `git add`/`git commit`, `git diff`, and
  the pack's codegen command — the last because hand-editing a generated file is forbidden
  outright, leaving an agent without codegen no legal path at all. `tests/framework_checks.py`
  § phase-3 permissions pins this. Harness parity does **not**: it compares agent bodies, and
  frontmatter legitimately differs between harnesses, so nothing else guards these tokens.

  It is worth stating why that check exists. The matrix was originally derived from an assumed
  task shape rather than from what the pipeline instructs, and it drifted out of agreement
  silently: the `test` agent could not run the base check its own protocol mandates, nor commit,
  so a human committed for it; and a task needing two toolchains had no agent at all. Neither is
  visible from reading any single file. When you widen a grant, prefer named verbs over
  `Bash(git*)` — `test` and `scaffold` deliberately hold neither `git push` nor `git reset`,
  because the isolation protocol tells agents never to reset their way out of a base mismatch
  and a permission states that more firmly than a sentence in a prompt does.

  **This is a Claude Code contract only.** omp agents hold bare `bash`, so a task that cannot run
  here may run there. That asymmetry is a reason to report a permission gap rather than work
  around it — see the cycle skill § When no agent holds the permission a task needs.
- **Data-layer schema checks** — `review`, `verify`, `test-rubric`, and `adversarial-tester`
  contain a **context-gated** schema-drift check that activates only when a data-schema
  Context Source is enabled. With none wired, the check is skipped and noted as not performed.

## `scaffold/` pattern shapes

`agents/scaffold/*.md` are **language-neutral** shapes: all 23 GoF design patterns plus three
architecture shapes (`interface`, `service`, `use-case`). They describe structure; the concrete
idiom comes from the active pack's `scaffold-snippets.md`, which indexes one snippet file per
shape under `packs/<lang>/snippets/`.

`agents/scaffold/INDEX.md` is the **routing table** — the scaffold agent reads it, matches on the
`Triggers` column, checks the `Disambiguation` table, then opens exactly one pattern file. This
keeps pattern selection to one file read instead of a directory scan.

Every pattern file follows the nine-section standard in `skills/scaffold/pattern-template.md`
(`bridge.md` is the reference implementation). `/setup-scaffold` can add `Type: project-specific`
files that override a shape via a `Replaces:` header; it must also register them in `INDEX.md`,
since an unregistered file is invisible to the agent.

## Where a new rule goes

**A rule belongs in the file its actor reads.** Subagents never read
`skills/cycle/SKILL.md` — each reads only its own definition here, plus whatever the
orchestrator injects into its spawn prompt. So a rule only a subagent can obey or break
belongs in that subagent's body, and putting it in the cycle skill means the orchestrator
is told about behaviour it cannot perform.

This is not a style preference. Measured across 79 findings in 13 run reports
(2026-09-08 to 09-12, `docs/internal/deployment-and-ergonomics-plan.md` § 5):

| | |
|---|---|
| findings from an instruction the skill never gave | **63 (80%)** |
| from an instruction that could not work as written | 9 (11%) |
| from a rule addressed to an actor who does not read it | **3 (4%)** |
| from an actor that had the rule and misapplied it | 4 (5%) |
| from an instruction plausibly unread because the file is long | **0** |

The last row is why `SKILL.md` is not split by length. The third row is this section: the
`&&`-chain rule had been in the cycle skill for three rounds, addressed to the orchestrator,
while the agents breaking it — `verify` restoring a tree after falsification — had never been
told. It cost 4m19s in one clone and 8 minutes across one round.

The test, when a finding arrives: **who performed the action?** If a subagent did, the rule goes
in that agent's body, in every agent that could perform it — not only the one that happened to
fail. `harness_parity.py` pins these bodies across both harnesses, so a rule added to one side
and forgotten on the other fails the check rather than drifting.

Rules the orchestrator performs — spawning, committing, dispatching CI, writing the run report —
stay in the cycle skill.

**The corollary: some actors have no file.** A built-in harness agent such as `Explore` runs
the action but has no body the framework owns and no frontmatter it can scope, so the rule
cannot go where its actor reads. For those, the rule is **injected into the spawn prompt by
the skill that spawns it**, and the canonical text lives in one skill so the paste is a copy
rather than a paraphrase — see `evidence` § Method rules for a search subagent, which
`refine` Step 2 and `create-prd` Step 2 both paste. The same reasoning decides grants: a
per-script Bash grant can only be held by an actor whose frontmatter we write, so the script
goes to the main thread and the subagent gets rules.
