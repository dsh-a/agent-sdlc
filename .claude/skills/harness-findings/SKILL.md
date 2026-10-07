---
name: harness-findings
description: The probe checklist, severity scale, and format for the per-cycle harness findings section of a run report. Captures process faults — what the harness cost the cycle — separately from whether the work shipped. Single source of truth for harness fault-finding.
disable-model-invocation: true
---

# Harness Findings

A cycle can pass every product metric and still have cost hours to harness faults.
The 2026-08-24 myapp cycle finished with verify PASS 8/8, review APPROVE, and 2902
tests green — and three of four isolated agents had been building against a tree
roughly 90 commits stale, a supervisor that was enabled never ran once, and a
pre-flight agent asserted test coverage that did not exist. None of it appeared in
the run report's metrics, because the metrics were healthy.

That is the gap this section fills. **Every finding here is a process fault, not a
product one.** "Did the feature ship?" is answered elsewhere; this answers "what did
the harness cost us getting there?"

---

## The discipline

- **A green cycle is not evidence of no findings.** The cycle that produced this
  checklist was green. Zero findings is a legitimate outcome, but it means every
  probe below was checked and came back clean — not that nobody looked.
- **Every finding cites evidence.** A report path, an agent id, a file:line, a
  quoted line from an agent's return. A finding without evidence is a hunch and
  belongs in Recommendations instead.
- **Findings are about the pipeline, not the feature.** A bug in the app is a bug;
  file it per § Bug tracking. A bug in *how the pipeline built the app* is a finding.
- **Self-assessment is the weak point.** The orchestrator writes this section about a
  cycle it ran, and two of the original findings were orchestrator errors it did not
  notice at the time. Prefer evidence from agent returns and artifacts over
  recollection, and when an agent's report contradicts your memory, the report wins.
- **A gate failing is evidence.** After seven instrumentation failures in one session, an
  agent opened its response to a malformed-table report by calling the gate "almost
  certainly" wrong about its own cell counting. The gate was right: the file held literal
  `\|\|` pairs, six raw pipes against a four-pipe header, rendering as a five-column row
  inside a three-column table — visible garbage, failing silently, exactly the defect class
  the gate existed to catch. That your probes have usually been the culprit is not grounds
  for assuming it this time. Disprove a gate with a fresh read of the artifact, never with
  recollection. (`evidence` § The discipline owns this rule.)

## Severity

| | Meaning |
|---|---|
| **P0** | Corrupted or nearly corrupted the work. An agent built against the wrong state, or a result was accepted that should not have been. |
| **P1** | Cost significant rework, or caused the orchestrator to reason from a false picture. |
| **P2** | Wasted effort or produced a wrong claim that a later stage caught. |
| **P3** | Friction, silent degradation, or a heuristic that misfired without harm this run. |

## Probes

Work the list. Each is answerable from artifacts, not memory. The provenance column
names the original finding each probe generalizes — these are not hypothetical.

| # | Probe | Where the evidence is | From |
|---|---|---|---|
| 1 | Did any agent's workspace disagree with its briefing? | Agent returns mentioning a base mismatch, code contradicting the task, or a self-issued `git reset --hard` | P0 worktree base |
| 2 | Did any agent fail to read or write a pipeline artifact the skill says exists? | Returns reporting a missing task file, copying artifacts into a worktree, or asking the orchestrator to do file I/O | P1 gitignored tasks |
| 3 | Did an agent spawned read-only write to the tree? | Its `## Files changed` section vs. the scope you spawned it with; unexplained tree diffs | P1 review auto-fix |
| 4 | Was any component enabled in config but never activated? | Supervisor spawns = 0, Context Sources all `disabled`, hooks producing no events, a skip flag that never fired | P1 supervisor |
| 5 | Did a later stage contradict an earlier stage's claim? | A verify finding on an AC that pre-flight called covered; a review finding on code a test agent called tested | P2 pre-flight coverage |
| 6 | Did anything described as idempotent change when re-run? | Duplicate managed blocks, repeated appends, a guard that re-fired | P2 gitignore guard |
| 7 | What did the cycle leave behind that nothing owns? | Stray worktrees, branches, temp dirs, state files after Finalize. **Under a fan-out, check the clone itself** — `ls <clones-root>` and `git worktree list`, not just `git branch --list 'omp/task/*' 'worktree-agent-*'`. A fan-out 4 report answered this probe clean while three finished clones held 5.4G, because it read "worktrees" as Phase-3 task worktrees only | P2 cleanup owner |
| 8 | Did a best-effort step degrade silently? | A script that was absent, a fallback taken without a message, a step that logged nothing | P3 missing script |
| 9 | Did a heuristic misfire? | Mode suggestion vs. accepted; verify depth vs. what the change actually warranted | P3 mode heuristic |
| 10 | Did the orchestrator absorb work an agent should have done? | Central checkbox ticking, orchestrator-written files an agent was told to write | cross-cutting |
| 11 | Did an agent report an observation it did not make? | Verify's Step 4c re-run vs. the `test` agent's falsification blocks; any quoted output that does not name the test or line it claims to come from | P1 falsification did not reproduce |
| 12 | Did any permission prompt appear? | The session transcript — a prompt, a denial, or an agent reporting it could not run something. **Evidence exists only while the cycle runs** | P1 no agent holds what task 1.0 needs |
| 13 | Did an agent cite a source it did not read? | Quoted phrases in an agent's return, re-checked against the source they name with `evidence.py cite`. A grounding subagent once attributed a sentence to a GitHub issue body it had read from a source-code comment one row earlier in its own report — the phrase appears 0 times in that issue | P1 fabricated citation |

A probe with nothing to report is answered "clean" — do not write a row for it.

Probe 13 is cheap and worth running even on a clean cycle: a citation and the conclusion it
supports fail independently, so a correct finding can carry a fabricated attribution and no
review of the conclusion will catch it. See `evidence` § Checking a subagent's citations.

### Probe 12 wants more than a list

A permission prompt is the only finding here whose evidence is gone the moment the cycle ends —
nothing writes it to the run report, the telemetry or the gate log. So capture it while you can,
and capture enough to act on. For each prompt:

| Field | Why |
|---|---|
| **Agent** | Grants are per-agent. "The cycle needed `gh`" is not actionable; "`review` needed `gh run view`" is |
| **Exact command** | The narrowest grant that would have worked, not the family it belongs to |
| **What it was doing** | A permission needed once by one task is a different problem from one every cycle needs |
| **Outcome** | Approved, denied, or worked around — and if worked around, by whom. An orchestrator doing an agent's work is probe 10 |

Then answer the question that decides the fix: **a grant, or a script?**

The framework already answers it both ways, deliberately. `clear-agent-states.py` exists because a
narrow `rm` grant cannot be expressed — a glob permission is a string match, satisfied by a `cd ..`
first. `run-suite.sh` exists because the model must decide *when* to run tests while something else
decides *how*, so the watchdog is not tripped. `prune-analyzer-baselines.py` exists because deleting
from a shared vault needs a dry-run default that a permission cannot provide.

Use this to choose:

- **A grant** when the command is safe in every form the agent could construct, and the agent must
  choose the arguments. `Bash(git log*)` for an agent that reads history.
- **A script** when *what* is safe depends on scope the permission cannot express (a path, a
  directory, a target), when the operation is destructive or outward-facing, or when the safe usage
  is a sequence rather than one command. The model decides when; the script enforces what.
- **Neither — split the task** when one task needs two toolchains no single agent should hold. See
  the cycle skill § When no agent holds the permission a task needs.

Record your answer with the finding. A prompt that recurs and is approved each time is a grant
waiting to be written down; one that recurs and is worked around each time is a script waiting to be
written.


## What worked, and is worth keeping

Findings are only half of it. The original document's "what worked" section is what
promoted **forced falsification** — break the guard, watch the test fail, restore it,
quote the failure — from a per-prompt instruction into the standing `test` agent
definition, where it now catches the permissive-matcher trap for every future cycle.

Record anything that worked *because of how the run was set up rather than what was
built*, especially a behaviour that lived in a one-off prompt. A practice that only
works when someone remembers to ask for it is not yet part of the pipeline.

## Format

Append to the run report:

```markdown
## Harness findings

Process faults from this cycle, independent of whether the work shipped.
Outcome: [verify verdict] · [review verdict] · [test count] — findings below are
about the pipeline, not the feature.

### P1 — [short title]

[What happened, in two or three sentences. What it cost.]

**Evidence:** [report path / agent id / file:line / quoted return]
**Suggested fix:** [what would prevent a recurrence, or "unclear — needs triage"]

### What worked, and is worth keeping

- [Behaviour, and whether it should be promoted into an agent or skill definition]
```

Write `None — probes 1-12 checked, all clean.` when there is genuinely nothing.
That sentence is a claim that the checking happened; do not write it otherwise.

## Downstream

`self-improve` reads these across cycles. A finding that recurs in three or more runs
is a pipeline defect rather than an incident, and gets a recommendation at high
confidence — see `pipeline-metrics-rubric` § Harness finding patterns.

A P0 or P1 finding is worth acting on immediately rather than waiting for a pattern
to accumulate. One occurrence of "agents built against the wrong base" is enough.
