# Tests

Two layers. Install deps once: `pip install -r tests/requirements-dev.txt`.

## Layer 0 — stdlib only, no install (`check.py`)

A subset of Layer 1 with **no third-party imports**, so it runs anywhere —
including in an agent session that cannot install packages. Covers the
structural invariants and harness parity; the full suite still covers more.

```bash
python3 tests/check.py
```

Reach for this when `pytest` is unavailable. It is not a CI gate — Layer 1 is.

## Layer 1 — static validation (`test_structure.py`)

No models, no harness. Parses the framework's own Markdown + YAML and asserts
internal consistency — broken `§` references, stale paths, invalid/duplicate-key
YAML, dangling skill names, missing pack files, Claude-Code-only tokens leaking
into `.omp/` bodies. Runs in <1s.

```bash
pytest tests/test_structure.py -q
```

Layer 1 imports two stdlib modules that are also runnable on their own:

| Module | Checks | Run directly |
|---|---|---|
| `framework_checks.py` | code-fence balance, scaffold nine-section schema, `scaffold/INDEX.md` coverage, pack snippet index | `python3 tests/framework_checks.py` |
| `harness_parity.py` | `.claude/agents` ↔ `.omp/agents` divergence, pinned to `fixtures/harness-parity.diff` | `python3 tests/harness_parity.py` |
| `context_budget.py` | static token load per agent + orchestrator baseline, pinned to `fixtures/context-budget.json` | `python3 tests/context_budget.py` |

### Harness parity

Every agent is defined twice — once for Claude Code, once for omp — and the two
legitimately differ (irc vs. file transport, `lsp` vs. IDE diagnostics, `task`
vs. `Agent(...)` spawns). Nothing enforced the rest matching, so a fix applied
to one side and forgotten on the other drifted silently.

The divergence is now **pinned**, not forbidden. Editing one side only changes
the recorded diff, which surfaces in review as a change to
`tests/fixtures/harness-parity.diff`. After an intended change:

```bash
python3 tests/harness_parity.py --update
```

Re-record deliberately — the point is that the new divergence gets read by a
human before it lands.

Hard gate in CI on every push/PR (`.github/workflows/validate.yml`). This is the
regression guard for the class of bug found in the release review.

## Layer 2 — model-backed assessment (`assess.py`)

Runs two probes against a real model via **OpenRouter**:

- **A. Doc-consistency judge (advisory)** — an LLM audits `README.md`,
  `CLAUDE.md`, and `.omp/agent-config.md` for internal contradictions and writes
  `tests/assess-report.md`. Never fails the build (findings are for a human to
  triage).
- **B. Agent-contract smoke (hard)** — feeds the shipped `review` agent prompt a
  buggy fixture diff (`tests/fixtures/buggy_diff.diff`) and asserts it returns a
  well-formed, on-topic review. Fails only on an empty/off-topic response.

```bash
OPENROUTER_API_KEY=sk-or-... python tests/assess.py         # cheap default model
MODEL=anthropic/claude-sonnet-4.5 OPENROUTER_API_KEY=... python tests/assess.py
```

Skips cleanly if `OPENROUTER_API_KEY` is unset. In CI (`.github/workflows/assess.yml`)
it runs on **manual dispatch + a weekly schedule** only — not every push — to protect
the funded OpenRouter account, defaults to a cheap model, and uploads the report as an
artifact. Add the key as the `OPENROUTER_API_KEY` repo secret to enable it.

> **Recommended:** use a **dedicated** OpenRouter key with a **spend cap** set in
> OpenRouter for CI (not your main key) — bounds the blast radius and lets you rotate
> it independently. The key is never exposed to fork PRs, and the only workflow that
> uses it (`assess.yml`) runs on manual dispatch + schedule, never on untrusted PR code.

### Context budget

Every agent costs tokens before it does anything: its body plus every skill it
autoloads. `docs/internal/local-llm-refactor-plan.md` measured that load on
2026-08-29; re-measured on 2026-09-20, `cycle/SKILL.md` had grown 74% and the
orchestrator baseline 60% — **+13,117 tokens on every cycle**, from fifteen
reasonable edits that nobody was in a position to see the sum of.

Like harness parity, the load is **pinned, not forbidden**. Growth beyond a small
tolerance turns the suite red; you either trim it or re-record, and the re-record
puts the increase in the PR diff as a line a reviewer approves.

```bash
python3 tests/context_budget.py            # check
python3 tests/context_budget.py --update   # re-record after an intended change
python3 tests/context_budget.py --report   # markdown tables + cumulative drift
```

Two things it surfaces that editing a file cannot:

- **Shared skills multiply.** `whispers` is autoloaded by five agents, so a
  paragraph added to it is paid five times per Phase-3 wave.
- **Cumulative drift.** `--report` prints the total against the recorded date, so
  many small additions that each stay under tolerance still stay visible.

Tokens are chars/4 — the same approximation the design docs use, so the numbers
stay comparable. It measures drift, where a systematic bias cancels.

### Peak context

The companion measurement to the context budget. That one measures what an agent
costs *before* it starts; this measures the largest prompt it actually held, from
transcripts of runs that already happened.

```bash
python3 .claude/skills/cycle/peak-context.py --match cycles-myapp
python3 .claude/skills/cycle/peak-context.py --agent test     # per-session
python3 .claude/skills/cycle/peak-context.py --json
```

Peak is `input_tokens + cache_read + cache_creation` — the cache split is a
billing distinction, not a context one, and a cached token still occupies the
window. Attribution comes from the `<transcript>.meta.json` sidecar the harness
writes at spawn, so agent types are exact rather than inferred.

`~/.claude/projects` rotates, so a reading is not reproducible later. `--snapshot`
appends the per-agent summary — never per-session rows — to
`docs/internal/data/peak-context-history.jsonl`, stamped with date, corpus size
and framework commit. One line per reading; run it deliberately, like
`context_budget.py --update`.

Guarded by `tests/test_peak_context.py` (synthetic transcripts; no dependency on
anyone's `~/.claude`), which pins the two ways this goes quietly wrong: summing
duplicate usage blocks, and reading only `input_tokens` — near zero on a cached
turn, which would report an agent holding 2 tokens of context.

## Layer 2b — the qualification matrix (`qualify.py`)

Which models can run which agents. Every probe drives the **shipped**
`.omp/agents/*` body as its system prompt, against fixtures with known-correct
answers, and scores two things separately: `correct` (reached the right decision)
and `format` (obeyed the response contract). A model can be right and
unparseable, or tidy and wrong, and the fix differs.

```bash
python3 tests/qualify.py --selftest          # graders + probe shapes, no network
python3 tests/qualify.py --dry-run           # what would run, and how many calls
OPENROUTER_API_KEY=... .venv/bin/python tests/qualify.py --repeat 3
MODELS="qwen/qwen3-235b-a22b" .venv/bin/python tests/qualify.py
python3 tests/qualify.py --reasoning off     # the B2 thinking probe
```

Writes `docs/internal/qualification-matrix.md`. Never fails a build — a weak
model scoring badly is the measurement working. Exit 2 is reserved for the rig
itself being broken, which must never be recorded as a model result.

Probes are data under `tests/probes/<agent>/<case>.json`, so adding a case is a
file, not a code change. Two conventions worth keeping:

- **Include the negative case.** `review/clean-diff` asserts a pure rename is
  *not* reported as a bug. False-positive rate is what makes a reviewer unusable
  and a keyword sniff cannot express it.
- **Use `--repeat`.** At n=1 a model's variance reads as a verdict. Every
  interesting finding so far only appeared at n=3.

An expected label may be a list, meaning any of them is correct. That exists
because one fixture turned out genuinely ambiguous; adjudicating it would have
measured agreement with the fixture's author rather than competence.
