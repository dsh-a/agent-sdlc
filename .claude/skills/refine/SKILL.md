---
name: refine
description: Refine a story issue toward INVEST compliance and Definition-of-Ready. Interactive dialogue — grounds the story against the codebase, probes every acceptance criterion, keeps a refinement log in the issue comments, and emits a DoR verdict. Can split stories into sub-issues.
disable-model-invocation: true
---

# Refine — Story Refinement Dialogue

You are refining a single user story toward INVEST compliance and a Definition of Ready (DoR)
verdict. The product is a **better story**, not a report. The refinement log is supporting evidence.

The story issue to refine: **$ARGUMENTS** (an issue number, `#412`, or a URL).

If `$ARGUMENTS` is empty, list candidates (`gh issue list --label story`) and ask which one.
Do not proceed without one.

Stories live in GitHub — see `.omp/agent-config.md` § Artifact Paths. Every read is a live `gh`
call. **If a `gh` call fails, stop and report it.** Never write the story to a local file instead.

`rationale.md`, beside this file, holds the measurements behind the rules below. Read it when a
rule looks arbitrary; do not load it to follow one.

---

## Operating principles

- **The issue body is destructively rewritten** as discovery happens. It holds the live spec,
  the `## Open questions` queue, and `## Open spikes`.
- **The refinement log is issue comments** — one per pass, append-only. Never edit a prior pass.
- **Splits are non-destructive.** Children are new sub-issues; the parent keeps its prose and
  gains a split notice.
- **One home per fact.** Status, parentage and ordering are GitHub primitives, never prose:

  | Fact | Home |
  |---|---|
  | Refinement maturity (DRAFT / REFINING / REFINED / BLOCKED) | board field `Refinement` |
  | Pipeline status | board field `Status` — `cycle` owns it |
  | Parent / children | sub-issues |
  | Depends on | issue dependencies (`blocked_by`) |
  | Depended on by | **derived** — read the `blocking` direction; never stored |

  Write one direction; read the other.
- **DoR is advisory.** Emit the verdict; block no other workflow on it.
- **Dialogue, not monologue.** Surface ambiguities as questions. Do not invent answers.
- **The user reads the story twice** — Step 1 for orientation, Step 8 for sign-off. `REFINED` is
  what lets `/cycle` build from this body unattended, so it needs an explicit yes.
- **Persist the queue** to the issue body after every batch, so the dialogue resumes across
  sessions.

---

## Model & effort allocation

Delegate read-heavy mechanical work to the smallest viable model. The main thread handles
reasoning, dialogue and final writes.

| Step | Work | Where | Model |
|---|---|---|---|
| 2 | Greps, file reads, schema lookups | `Explore` subagent | **haiku** |
| 2 | Citation + absence checks on what came back | main thread (`evidence.py`) | inherit |
| 3 | Probe verdicts | main thread | inherit |
| 4 | Dialogue | main thread | inherit |
| 7–8 | Split allocation, sign-off, verdict | main thread | inherit |

**Forbidden reads:** generated/codegen files (`*.g.dart`, `*.freezed.dart`, `*.g.cs`). Read the
hand-authored source instead, and pass this rule to every subagent.

---

## The scripts

Two scripts own everything mechanical. They print facts; you interpret them.

**`probes.py`** — pure text, no network:

| Verb | Gives you |
|---|---|
| `artifacts --body -` | every probeable artifact, with flags and each probe's workload |
| `probes` | the probe table below, which it is the source of |
| `coverage --body - --verdicts f.tsv [--prior g.tsv]` | the gaps, and the log's `**Probes:**` line |
| `queue read / next-id / add / resolve` | the `## Open questions` section |
| `profiles --path <file>` | the customer profiles, or `unavailable` |

**`story.py`** — the `gh` half:

| Verb | Gives you |
|---|---|
| `load <n>` | issue, labels, board fields, both dependency directions, and a gate verdict |
| `dor <n> --coverage <file>` | the DoR table as a gate; exit 1 names what is unmet |
| `set-depth <n> <full\|lean\|hotfix>` | the board write, after resolving four ids |
| `split <n> --plan <json>` | children, links, chain, notice, close |

Exit codes for both: `0` ok · `1` refused or unmet · `2` bad usage · `3` **could not determine**.
Writes are **dry by default**; `--apply` writes. A `3` is never a default — stop and report it.

---

## Step 1 — Load and validate the target

```sh
python3 .claude/skills/refine/story.py load <n>
```

One invocation replaces five `gh` calls and prints `gate=`:

| `gate=` | Do |
|---|---|
| `ok` | continue |
| `closed-superseded` | stop — it stopped existing. Refine what replaced it |
| `has-children` | stop — a split parent is closed to refinement. Refine the children |
| `already-refined` | ask the user before re-opening a previously-refined story |

**Restate the issue before touching anything.** The user typed a number; the number says nothing.
A wrong target caught here costs nothing, and caught after a body rewrite costs the body. The
script gives the facts and deliberately will not summarise the prose — that reading is yours, and
a wrong one is what this catches:

```
### #<n> <issue title> — as it stands

**Board:** Refinement <value> · Status <value> · Phase <value> · Depth <value or "unset">
**Links:** parent <#n or none> · children <#n… or none> · blocked by <#n…> · blocks <#n…>
**Labels:** <labels>

**What it asks for:** <2-4 sentences, from the body — not the title>

**Acceptance criteria as written:** <count, or "none stated">

**What this pass will attack:** <the 2-3 weakest points you can already see>

Refining this one? (y / different issue)
```

Then set `Refinement` to `REFINING`. If a fact you need has no field, set the field — do not
write it into the body as prose.

---

## Step 2 — Codebase grounding (delegated)

Extract every concrete claim, then delegate verification to an `Explore` subagent on **haiku**.
Do not grep or read large files on the main thread.

| Claim type | How the subagent verifies |
|---|---|
| File path | `Glob` / `Read` |
| Class / component / function name | `grep -r "class Foo\|Foo("` |
| Schema column / table | the hand-authored schema (NEVER generated files) |
| "Currently X is at Y" | grep + structural comparison |
| Cross-story reference | `gh issue view <n>` |

```sh
cat .claude/skills/refine/grounding-prompt.md
```

`grounding-prompt.md` holds the spawn prompt. **Paste it, and paste the fenced block from
`evidence/SKILL.md` § Method rules for a search subagent — do not retype or paraphrase either.**
`Explore` is a built-in harness agent whose body and tools the framework does not own, so the
prompt is the only channel those rules have. If `evidence` is unreachable at all three
`autonomous-agent` § Skill resolution paths, tell the user that delegated grounding would be
unverified and **ground on the main thread instead** rather than spawning blind.

### Check the citations before using any row

A conclusion and its citation fail independently — a grounding subagent once attributed a
sentence to an issue body when it had read it from a source comment one row earlier in its own
report, and the conclusion was sound.

Per `evidence` § Checking a subagent's citations: re-check **every citation bound for the issue
body, a child issue, a bug report or the Step 8 restatement**, and spot-check two others.

```sh
gh issue view <n> --json body -q .body |
  python3 .claude/skills/evidence/evidence.py cite --phrase '<quoted phrase>' --source -
```

`hits=0` strikes the **citation**, not the claim: the row reverts to ungrounded. Re-verify it
from a source you read directly, or make it a question. Never keep a claim with a bad citation;
never drop a claim because its citation was bad.

A row whose `Corpus searched` cell names fewer files than the claim's scope is also ungrounded:

```sh
python3 .claude/skills/evidence/evidence.py absence --pattern '<symbol>' <the real corpus>
```

Contradicted and not-found rows become questions in Step 3. Do **not** silently fix a
contradiction — "the story says X but the code says Y, which is right?" is the user's call.

---

## Step 2b — Prove the mechanism

**Trigger:** the story asserts that a tool, config file, framework or CI feature *behaves a
certain way*. Not every story has one.

Run it — in a throwaway project if the real repo would be disturbed — and record the command and
its **exact output** in the log. **Reading the documentation is not proving. A missing `--help`
flag is not proving.** Both are specific mistakes on record.

Three things make a proof worth having:

1. **The exact command and its exact output**, pasted, not summarised.
2. **The version it was proven against** — a mechanism is true of a toolchain, not forever.
3. **What it rules out.** The useful half is often negative.

**The proof is the pasted output, not the file.** Run it outside the repo where you can, and
delete it in the same step that records its output — "later" is the pass that leaked one
(`rationale.md` § Throwaways). **A probe inside the project's test glob is not a throwaway**: a
bare test run sweeps it and one `git add -A` commits it. Log where it ran and that it is gone, so
a reader can tell a deleted probe from one nobody looked for.

A story carrying an unproven mechanism claim is **not READY** (Step 8). `rationale.md` § Mechanism
has the case that pays for this step: a tag taxonomy that was rejected outright by the tool, in
seven open issues, found by running it.

---

## Step 3 — Probe every artifact

Refinement at its best is five people in a room: a **developer**, the **codebase** itself, a
**product manager**, an **agile coach** and a **quality engineer** — and, because none of those
five is the customer, the **customer profiles** the product serves. That is a good argument that
the probe set below is complete. It is a bad way to apply it: a persona tells you a motive, not
what to point at. So the unit of work here is a **probe over an enumerated artifact**.

```sh
gh issue view <n> --json body -q .body > /tmp/body.md
python3 .claude/skills/refine/probes.py artifacts --body /tmp/body.md
```

That prints every artifact with an id, and each probe's workload. Work one probe at a time and
record a verdict per artifact in a TSV — `probe<TAB>artifact-id<TAB>verdict<TAB>artifact-text`:

| Probe | Input | Asks |
|---|---|---|
| `inherited-claim` | each citation `ungrounded` | Is it true *today*? A claim inherited from the epic or a sibling is suspect by default — agreeing with the parent is a shared source, not corroboration |
| `measured-number` | each number `ungrounded` | Was it measured, or inherited? Name the measurement or demote it to a question |
| `mechanism-exists` | each mechanism `unproven` | Does it behave as claimed? Prove it (Step 2b). And is a sibling already building it? One mechanism across siblings, not two |
| `ac-strict` | each AC `open` | Could this be marked satisfied while the thing it protects is still broken, or could two engineers disagree that it passed? |
| `deferred-number` | each AC `threshold` | A deferred number is not an agreed one. Name it, or make it a question — an unnamed threshold is satisfiable by one that never fires |
| `concrete-deferral` | each prose deferral | What does the user see concretely — hidden, disabled, or visible-and-inert? |
| `named-edge` | each dependency xref | Is the edge filed, or invented? Two stories touching one subject are not dependent — record that you checked and found none |
| `independently-demonstrable` | each proposed child | Can it be demonstrated without running its sibling? A seam needs evidence, not a count |
| `profile-impact` | each customer profile | Does this serve or degrade this customer? "All of them equally" is the answer to distrust |

`probes.py probes` is the source of that table; if the two disagree, the script is right.

**`profile-impact` needs the project's profile file.**

```sh
PROF=$(python3 .claude/skills/cycle/config-get.py customer_profiles_path \
         --default product/customer-profiles.md)
python3 .claude/skills/refine/probes.py profiles --path "$PROF"
```

Exit 3 means `unavailable`. Say *unavailable* in the log — **never `clean`** — and tell the user
the file is missing. `customer-profiles.template.md` beside this file is the contract. The sharp
questions, once profiles exist: which profile is this **designed for** (all of them equally is
suspect); which one does it **degrade**; which one would never **discover** it. Worst-case data
volume belongs to a named profile, not to nobody.

Each question you raise must be self-contained and answerable in 1–2 sentences. Keep the
`(AC) (Behavior) (Scope) (Data) (Deps) (Risk) (Size)` tags — they are in flight in open issues.

**The queue is epic-wide, not per story.** `Q-19` raised on one story is answered on another and
cited by a third, and a story inherits the parent's deferred questions on arrival:

```sh
python3 .claude/skills/refine/probes.py queue next-id <every sibling body>
```

Never number from 1. When an answer changes a sibling, say so there too (Step 6b).

**Persist the queue** to the issue body under `## Open questions` after the queue is built and
after each batch. `probes.py queue add` and `resolve` print the whole modified body for
`gh issue edit --body-file -`, changing exactly one line:

```markdown
## Open questions

<!-- Auto-maintained by /refine. Edit answers here only if you want them treated as resolved. -->

- [ ] (Behavior) Cross-phase drag — can a set move between phases?
- [x] ~~(Data) `_routineExerciseSets` actual type?~~ → `Map<String, List<ExerciseSet>>` (resolved 2026-04-28)
```

On every re-invocation, read this section first. Unchecked items are the active queue. If the
user checked items or wrote answers between sessions, fold those in without re-asking.

---

## Step 4 — Dialogue with adjustable batch size

State at the start of each batch: `Q-batch mode: N (default 1)`.

Default batch size is **1**. The user may say "switch to 2/3/1" at any time:

- **Increase (1 → 3):** re-ask the pending question plus the next (N − current), as one batch.
- **Decrease (3 → 1):** re-ask only the first; push the rest back onto the queue's front in order.

Use `AskUserQuestion`. Title: short noun phrase. Header: the 1–2 word category tag. Question:
full text, self-contained. Options: 2–4 plausible answers plus "Other (specify)" when reasonable.

After each batch:

1. Apply each answer — rewrite the body section, update ACs, add scope notes or a spike. A
   dependency answer becomes an **issue dependency**, not prose:
   ```sh
   # the endpoint takes the integer database id, not the issue number
   BLOCKER_ID=$(gh api "repos/$REPO/issues/<blocker-n>" --jq .id)
   gh api -X POST "repos/$REPO/issues/<n>/dependencies/blocked_by" -f issue_id=$BLOCKER_ID
   ```
2. Hold the Q+A pair for this pass's log comment.
3. Update `## Open questions`: resolve answered items, append follow-ups.
4. Push the body edit **before** asking the next batch, so an interrupted session resumes.

Continue until the queue is empty and the last round produced no new questions. Then re-run
`probes.py artifacts` — a rewritten body has new artifacts — and `coverage`.

---

## Step 5 — Maintain the refinement log

One issue comment per pass, posted at the end of the pass, never edited afterwards.

```sh
python3 .claude/skills/refine/probes.py coverage --body /tmp/body.md \
  --verdicts /tmp/verdicts.tsv --prior /tmp/last-pass.tsv
cat .claude/skills/refine/templates.md          # § The refinement-log comment
gh issue comment <n> --body-file -
```

Paste the `**Probes:**` line `coverage` printed. A coverage line you wrote by hand is a claim;
one the script printed is a count — and gaps mean the pass is not done. `rationale.md` § Probes
have been the culprit explains why the log separates instrument failure from content failure.

## Step 6 — Open spikes

When a question needs investigation rather than a decision, add an entry under `## Open spikes`
in the **issue body**:

```markdown
## Open spikes

- **[SPIKE-1] Schema impact of version-badge field**
  Question: stored int column, or derived from a save_count tracked elsewhere?
  Blocks: AC "version badge persists across sessions"
  Time-box: 2 hours
```

This skill does not auto-file spike issues. A story with one or more open spikes ends
`Refinement = BLOCKED`.

## Step 6b — Propagate a correction

A correction that stays in one story fixes one story. When this pass contradicts something
**inherited** — from the epic, a sibling, or a cited document — it has to reach the source.

1. Find who else carries the claim: `gh issue list` over the epic's sub-issues, plus anything
   the story cites.
2. Correct each, with a one-line provenance footnote — what changed, which pass found it, and on
   which issue.
3. **A closed issue is left alone** and noted as archival. Reopening it to correct prose nobody
   will read again is churn.
4. Record the fan-out in this pass's log — *"corrected in #415, #416, #543"* — so the next reader
   can tell a propagated fix from an isolated one.

---

## Step 7 — Decide whether to split

After the queue is empty, evaluate against INVEST:

| Letter | Check |
|---|---|
| **I**ndependent | Can this ship without other unrefined stories? |
| **N**egotiable | Is scope intentional and explicit? |
| **V**aluable | Is the user-visible outcome clear? |
| **E**stimable | Can the team size it? |
| **S**mall | One cycle, one PR? |
| **T**estable | Is every AC verifiable? |

**A seam needs evidence, not a count.** Say what makes the cut real: which child is
independently demonstrable, and what forces them apart. Both directions need the same kind of
reason — `rationale.md` § Seams records a split justified by two open defects, and a three-way
split rejected in the same pass because a fixture child had no demonstrable value alone.

If **S** fails, propose the split shape, then the prose allocation, then write. Three
confirmations, because each is cheaper to reject than the next:

```
Proposed split of #412:
  A — Shared component extraction (OrderSearchPanel, SimilarOrderSheet, DropZone)
  B — View-model data-model migration (Map→List, new methods)
  C — Two-pane layout + structural panel
Confirm split, adjust, or cancel?
```

On confirmation, propose the **prose allocation** the same way — which sections and which ACs go
to each child, and what stays in the parent as archival — and take a second confirmation before
writing anything.

**Check the allocation mechanically before writing anything.** Every parent AC must land in
exactly one child: in two is duplicated work, in none is a silently dropped requirement.

```sh
python3 .claude/skills/evidence/evidence.py enumerate --unit checkbox \
  --before parent.md --after child-a.md --after child-b.md --after child-c.md
```

`verdict=anomalous` names each `unplaced` and `duplicated` AC. Resolve both with the user — a
dropped AC is far cheaper to find here than in `verify`.

Then write the children. Title them plainly; **do not invent `<parent>.<n>` ids** — the issue
number is the identity, and `epic:` labels are generated from the sub-issue tree, never
hand-written.

```sh
python3 .claude/skills/refine/story.py split <n> --plan plan.json          # dry run
python3 .claude/skills/refine/story.py split <n> --plan plan.json --apply
```

```json
{"notice": "> **Split on 2026-04-28** into …\n>\n> Closed to further refinement. Original prose retained below for archival; the children carry the live specification.",
 "children": [{"title": "Shared component extraction", "body_file": "child-a.md"},
              {"title": "View-model data-model migration", "body_file": "child-b.md",
               "after_previous": true}]}
```

The script creates children, links them as sub-issues, chains `after_previous` as dependencies,
inherits the parent's `blocked_by` onto the first child, prepends the notice and closes the
parent `not planned` + `superseded:split` — **in that order**, because an edge needs both numbers
and a parent closed early leaves a half-split story unrefinable. Set each child's `Refinement`
to `DRAFT`. Then post the pass's log comment on the parent with the split rationale.

The parent's prose, ACs and log comments all remain. Nothing is deleted.

### Offer to refine children in the same session

```
Children created. Refine them now, or stop here?
  [1] Refine the first child next (recommended — keeps context warm)
  [2] Refine all children sequentially
  [3] Stop. I will re-invoke /refine per child later.
```

On (1) or (2), recurse from Step 1 on the chosen child. Pass the existing grounding table in as
a known-good baseline for claims already verified this session; still ground anything new.

---

## Step 8 — Restate, take sign-off, set final status

**Nothing here is written until the user has signed off.** Decide the verdict and the depth,
show the user the whole story, then edit the board.

```sh
python3 .claude/skills/refine/story.py dor <n> --coverage /tmp/coverage.txt
```

Exit 1 names what is unmet. Two conditions the script cannot check are yours to assert: INVEST,
and that every CONTRADICTED grounding row was resolved rather than dropped.

| Verdict | Condition | `Refinement` |
|---|---|---|
| **READY** | INVEST passes; no open spikes; no unresolved contradiction; every mechanism claim proven (Step 2b); `probes.py coverage` reports zero gaps; `Depth` set | `REFINED` |
| **NEEDS-SPLIT** | INVEST-S fails; user did not confirm the split | `REFINING` |
| **BLOCKED** | One or more open spikes | `BLOCKED` |
| **SPLIT** | Split this pass | — closed `not planned` + `superseded:split` |

Do not touch `Status` — `cycle` owns it. Do not stamp a `refined_at`: the last log comment's
timestamp is that date.

### Set `Depth` — required for READY

A `REFINED` story must say how deep a cycle it warrants, in the board's **`Depth`** field
(`full` / `lean` / `hotfix`). `/cycle` reads it instead of asking, which is what lets a fan-out
run several stories at the right depth without one flag for all of them.

**This is the right place for the decision and nowhere else is.** `/cycle`'s own heuristics read
the *argument string*, and `/cycle BUG-088` matched every `hotfix` condition while the work
changed a ViewModel's lifetime across every entry path into a screen. You have just read the body
and grounded it. Nothing downstream will know more than you do now.

| `Depth` | Choose when |
|---|---|
| `hotfix` | One defect, one cause, one file or nearly. No new AC beyond "it stops doing that." **Never for a story** |
| `lean` | Small and behaviourally obvious. The ACs you wrote this pass *are* the spec. No schema or migration, one layer, no new cross-story contract |
| `full` | Anything touching schema, a migration, more than one layer, a shared component other stories consume, or where grounding changed the design. **Also whenever you hesitate** — `full` costs one extra human gate, and `lean`'s cost is measured (`rationale.md` § Depth) |

```sh
python3 .claude/skills/refine/story.py set-depth <n> full          # dry run
python3 .claude/skills/refine/story.py set-depth <n> full --apply
```

Exit 3 with `reason=no-depth-field` means the board has no such field. Say so in the verdict
block rather than inventing a home — a `Depth:` line in the body is exactly the second copy this
skill exists to prevent. `/cycle` degrades to asking.

### The sign-off restatement — required before `REFINED`

`REFINED` is a claim made to everything downstream: `/cycle` will build from this body without
re-reading the original, and a fan-out will run it unattended. The person who lives with that has
seen the story only one `AskUserQuestion` batch at a time. They answered about the parts; they
have never been shown the result.

So print the **complete** final story and ask for an explicit sign-off. Complete means the issue
body verbatim — not a summary, not a diff. It is the artifact they are approving.

```
### #<n> <issue title> — refined, pending your sign-off

**Proposed:** Refinement REFINED · Depth <full|lean|hotfix>
**Links:** blocked by <#n… or none> · blocks <#n… or none> · parent <#n or none>

--- issue body as it now reads ---
<the full body, verbatim, including every AC and any `## Open spikes`>
--- end ---

**Changed this pass:** <n destructive edits, n ACs added, n removed, n questions resolved>
  <!-- Do not count by hand. Predicted AC totals were wrong three times in one
       session while the edits were correct, and only an enumeration told the
       arithmetic error apart from an edit defect. Save the pre-edit body and run:
       evidence.py enumerate --before <saved> --after <current> --unit checkbox -->
**Probes:** <the line `coverage` printed>
**Depth rationale:** <one line — the specific finding that chose it>
**Grounding still unresolved:** <any CONTRADICTED/NOT-FOUND row you did not close, or "none">

Sign off and mark REFINED? (yes / changes needed)
```

Use `AskUserQuestion` for the sign-off itself, so the answer is unambiguous.

**On "changes needed":** do not argue and do not set `REFINED`. Leave `Refinement` at `REFINING`,
push what they said onto the front of the queue, and return to Step 4. A restatement the user
cannot reject is a notification, not a gate.

Skip this gate only when the verdict is not `READY` — `NEEDS-SPLIT`, `BLOCKED` and `SPLIT` all
mean "not done yet", and nothing downstream will act on them.

Only after sign-off, write `Refinement` and `Depth`. Then print the closing block —
`templates.md` § The closing verdict block, which reports `Signed off by user:` among the rest —
and stop. Do not auto-loop on children, do not auto-invoke other skills, do not commit.

---

## Notes for the agent

- The issue is canonical. Push the body edit after every batch.
- On re-invocation with `Refinement = REFINING`, read `## Open questions` and the latest log
  comment. Do not re-ask resolved items. Pass last pass's verdict TSV as `--prior` so unchanged
  artifacts carry forward.
- Never build a local index, mirror or export of the board. Reads are live `gh` calls.
- Never read or modify generated/codegen files.
- If the original prose is no longer recoverable from the result, the change is destructive and
  must be logged.
- All greps and code reads go through the haiku `Explore` subagent in Step 2. **`evidence.py` is
  not a grep for this purpose** — it returns one verdict line, and running it on the main thread
  to check a subagent's claim is the point of it.
- Evidence discipline (`evidence` owns these — reference, don't duplicate):
  - **An absence claim carries its corpus.** A NOT-FOUND over one file is a fact about that file.
  - **Could-not-determine is never absent.** A missing path, an unreadable file, a failed `gh`
    call, `profiles` exit 3 — each is a third outcome.
  - **Grep for the fact, never the phrasing you remember.** Enumerating your own phrasings finds
    a subset by construction.
  - **Read anchors; never retype them.** `evidence.py anchor` before any guarded edit to the
    body, `guarded-edit` to apply, so a batch cannot half-apply.
  - **A returned URL is acceptance, not content.** After a body edit:
    `evidence.py round-trip --local <file> --remote-cmd 'gh issue view <n> --json body -q .body'`.
  - **A gate failing is evidence.** That your probes have usually been the culprit is not grounds
    for assuming it this time — disprove a gate with a fresh read, never with recollection.
