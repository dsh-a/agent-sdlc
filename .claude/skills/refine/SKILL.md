---
disable-model-invocation: true
---

# Refine — Story Refinement Dialogue

You are refining a single user story toward INVEST compliance and a Definition of Ready (DoR) verdict. The product is a **better story**, not a report. The refinement log is supporting evidence.

The story file to refine: **$ARGUMENTS**

If `$ARGUMENTS` is empty, ask the user for a path to a story file (e.g. `documentation/stories/1.51.md`). Do not proceed without one.

---

## Operating principles

- **Story file is destructively rewritten** as discovery happens. The `## Refinement log` appendix and `## Open questions` queue are append-only across passes.
- **Splits are non-destructive.** New child files; parent retains original prose and gains a visible split notice. Never delete content from a parent.
- **Codebase grounds every concrete claim.** A path, widget name, schema column, or "currently X" assertion must be verified before it survives refinement.
- **DoR is advisory.** Emit the verdict; do not block any other workflow on it.
- **Dialogue, not monologue.** Surface ambiguities as questions to the user. Do not invent answers.
- **Persist the question queue** to the story file after every batch so the dialogue is resumable across sessions.

---

## Model & effort allocation

To keep the main thread cheap, delegate read-heavy and mechanical work to subagents with the smallest viable model. The main thread (running this skill) handles reasoning, dialogue, and final writes.

| Step | Work | Where | Model | Effort |
|---|---|---|---|---|
| 2 | Codebase grounding (greps, file reads, schema lookups) | `Explore` subagent | **haiku** | medium |
| 3 | Question queue construction | main thread | inherit | high |
| 4 | Dialogue with user | main thread | inherit | high |
| 5 | Refinement-log writes | main thread | inherit | low |
| 7 | Prose-allocation proposal for split children | main thread | inherit | high |
| 7 | Writing child files (mechanical carve-up after user confirms allocation) | main thread | inherit | low |
| 8 | Index table maintenance | main thread | inherit | low |

**Forbidden reads:** `app_database.g.dart` and any other `.g.dart` (codegen, can be 10k+ lines). Read `schema.dart` instead. Pass this rule to any spawned subagent.

When spawning the Explore subagent, pass `model: "haiku"` and a self-contained prompt that lists every claim to verify and the expected output format (a structured grounding table). Do not let the subagent read generated files.

---

## Step 1 — Load and validate the target

1. Read `$ARGUMENTS`. If the file does not exist, stop and report.
2. Parse YAML frontmatter. Required fields:
   ```yaml
   ---
   id: <string>
   title: <string>
   status: <DRAFT | REFINING | REFINED | SPLIT | BLOCKED>
   parent: <id or null>
   children: [<id>, ...]
   depends_on: [<id>, ...]
   depended_on_by: [<id>, ...]
   refined_at: <ISO date or null>
   ---
   ```
3. If frontmatter is missing or partial, generate it from the file's contents (story heading, dependency hints in prose) and ask the user to confirm before continuing.
4. If `status: SPLIT`, stop. A SPLIT story is closed to further refinement — refine its children instead.
5. If `status: REFINED` and `refined_at` is recent, ask: "Re-open refinement on a previously-refined story?" before continuing.
6. Set `status: REFINING` and write back the frontmatter.

---

## Step 2 — Codebase grounding (delegated)

Extract every concrete claim from the story into a list, then delegate verification to an `Explore` subagent on **haiku**. Do not perform greps or large file reads on the main thread.

Claim types to extract:

| Claim type | How the subagent verifies |
|---|---|
| File path (`lib/.../foo.dart`) | `Glob` / `Read` |
| Class / widget / function name | `grep -r "class Foo\|Foo("` |
| Schema column / table | Read `lib/data/database/schema.dart` (NEVER `.g.dart`) |
| "Currently X is at Y" / "X is a Z" | grep + structural comparison |
| Cross-story reference (e.g. "used by 1.6") | Read the referenced story file if present |

Spawn the subagent with a prompt like:

```
Verify the following claims about the codebase. For each, return one of:
  VERIFIED — claim matches reality (cite file:line)
  CONTRADICTED — claim is wrong (cite actual state)
  NOT-FOUND — referenced thing does not exist

Forbidden reads: any *.g.dart file.
Output a markdown table only — no prose.

Claims:
1. <claim>
2. <claim>
...
```

Set `model: "haiku"`. Receive the table back, store it in memory.

Contradicted and not-found rows become questions in Step 3. Do NOT silently fix contradictions — they are user-facing decisions ("the story says X but the code says Y — which is right?").

---

## Step 3 — Build the question queue

Walk the story and enumerate every ambiguity. The categories below are the minimum coverage:

### A. AC verifiability
For each acceptance criterion: is it testable as written? Could two engineers disagree on whether it passed? If yes, queue a clarifying question.

### B. Behavioral gaps
- Empty / boundary states ("what does empty look like?")
- Error states ("what happens when X fails?")
- Concurrent / sync states (offline-first apps especially — what does the user see during a conflict?)
- Cross-platform divergence (web keyboard, mobile gestures, large vs small screen)

### C. Scope boundaries
For every "out of scope" or "decoupled" mention: what does the user see *concretely*? (Hidden? Disabled? Visible-but-no-op?)

### D. Data / structural
- Migrations or schema impact
- Ordering, uniqueness, cardinality constraints not explicit in prose
- What happens to data when an entity is removed / changed

### E. Dependencies
- Upstream stories this depends on (must already be REFINED or shipped)
- Downstream stories that depend on this one (do they constrain its design?)
- Shared widgets / extracted components — does the extraction itself deserve to be a separate story?

### F. Risks
- a11y (screen readers, keyboard nav, drag-drop alternatives)
- Performance ceilings (worst-case data size?)
- Telemetry / analytics expectations

### G. Sizing & split signals
- Can this be delivered as one PR / one cycle? If not, where are the natural seams?
- Are there sub-deliverables that have independent value?
- Is there scope that could be deferred without breaking the story's core promise?

Each question must be self-contained, answerable in 1–2 sentences. Group related questions for the same batch where possible.

**Persist the queue.** After the queue is built (and after each batch in Step 4), write it to the story file under a `## Open questions` section. Format:

```markdown
## Open questions

<!-- Auto-maintained by /refine. Edit answers here only if you want them treated as resolved. -->

- [ ] (Behavior) Cross-phase drag — can a set move between phases?
- [ ] (Scope) AI `[⚡]` button when out of scope — hidden / disabled / no-op?
- [x] ~~(Data) `_routineExerciseSets` actual type?~~ → `Map<String, List<ExerciseSet>>` (resolved 2026-04-28)
```

On every re-invocation: read this section before doing anything else. Treat unchecked items as the active queue. If the user has manually checked items or written answers between sessions, fold those answers into the next pass without re-asking.

---

## Step 4 — Dialogue with adjustable batch size

State at the start of each batch: `Q-batch mode: N (default 1)`.

Default batch size is **1**. The user may say "switch to 2", "switch to 3", or "switch to 1" at any time. On a switch:

- **Increase (e.g. 1 → 3):** Re-ask the current pending question, *plus* the next (N − current) from the queue, as a single batch. The user re-answers the original question alongside the new ones.
- **Decrease (e.g. 3 → 1):** Re-ask only the first of the current batch. Push the rest back onto the queue's front in original order.

Use `AskUserQuestion` for batches. For each question:
- Title: short noun phrase
- Header: 1–2 word category from Step 3 (AC / Behavior / Scope / Data / Deps / Risk / Size)
- Question: full text, self-contained
- Options: provide 2–4 plausible answers + one "Other (specify)" option when reasonable

After each batch:
1. Apply each answer to the story (rewrite the relevant section, update ACs, add scope notes, add open spike, adjust frontmatter dependencies, etc.)
2. Append the Q+A pair to `## Refinement log` (see Step 5).
3. Update `## Open questions`: strike-through and resolve answered items, append any new follow-ups raised by the answer.
4. Save the file before asking the next batch (so an interrupted session is resumable).

Continue until the queue is empty AND no answer in the last round produced new questions.

---

## Step 5 — Maintain the refinement log

The `## Refinement log` section lives at the bottom of the story file. Each refinement pass appends a new dated subsection:

```markdown
## Refinement log

### 2026-04-28 — Pass 1

**Grounding:**
- VERIFIED: `ExerciseSearchModal` exists at `lib/ui/routine_builder/views/exercise_search_modal.dart`
- CONTRADICTED: story claimed `_routineExerciseSets` is a `Map<String, ExerciseSet>` — actual type is `Map<String, List<ExerciseSet>>`. User confirmed story prose was outdated; rewrote.

**Questions answered:**
- Q (Scope): What does the AI `[⚡]` button look like when out of scope? → Hidden entirely on this screen until 1.8 ships. Story updated.
- Q (Behavior): Cross-phase drag allowed? → Yes, sets can move between phases and from UNPHASED into a phase. Added AC.
- ...

**Destructive changes to story:**
- Replaced "Map<String, ExerciseSet>" with "Map<String, List<ExerciseSet>>" in Special Considerations.
- Added 4 new ACs (cross-phase drag, empty phase prune, save toast, version-badge persistence).
- Removed obsolete bullet about ExerciseSearchModal location (now grounded as already-extracted).

**Open spikes raised:** see `## Open spikes` (1 added).

**DoR verdict at end of pass:** NEEDS-SPIKE
```

Append-only. Never delete a prior pass's log entry.

---

## Step 6 — Open spikes

When a question cannot be answered without investigation (a design decision needs prototyping, an external constraint needs research, etc.), add an entry under `## Open spikes` in the story file:

```markdown
## Open spikes

- **[SPIKE-1] Drift schema impact of version-badge field**
  Question: should `routine.version` be a stored int column or derived from a save_count tracked elsewhere? Impacts migration scope.
  Blocks: AC "version badge persists across sessions"
  Time-box: 2 hours
```

The skill does NOT auto-create separate spike story files. If a spike is large enough to warrant its own story, note it in the log and let the user create it manually.

A story with one or more open spikes ends Step 7 with `status: BLOCKED`.

---

## Step 7 — Decide whether to split

After all questions are answered, evaluate against INVEST:

| Letter | Check |
|---|---|
| **I**ndependent | Can this ship without other unrefined stories? |
| **N**egotiable | Is scope intentional and explicit? |
| **V**aluable | Is the user-visible outcome clear? |
| **E**stimable | Can the team size it? |
| **S**mall | Can it be delivered as one cycle / one PR? |
| **T**estable | Is every AC verifiable? |

If **S** fails (story is too large), propose a split. Present the split plan to the user before writing any files:

```
Proposed split of 1.51:
  1.51.1 — Shared widget extraction (ExerciseSearchPanel, SimilarExerciseSheet, AdjustAllSheet, DropZone)
  1.51.2 — ViewModel data-model migration (Map→List, new methods)
  1.51.3 — Two-pane layout + structural panel (dual-mode, search integration)
  1.51.4 — Right canvas + chip nav + phase sections
Confirm split, adjust, or cancel?
```

If the user confirms the split shape, **do not write child files yet**. First propose the prose allocation:

```
Proposed prose allocation for split:

  → 1.51.1 (Shared widget extraction):
     - Component inventory rows: ExerciseSearchPanel, SimilarExerciseSheet, AdjustAllSheet, DropZone
     - Special Considerations bullets 3, 4, 5, 6
     - ACs: (none directly — extraction is pre-work)

  → 1.51.2 (ViewModel data-model migration):
     - ViewModel additions table (entire)
     - Special Considerations bullet 1 (Map→List)
     - ACs: (none directly — internal refactor)

  → 1.51.3 (Two-pane layout + structural panel):
     - Screen Layout section
     - Left panel description
     - ACs: 1, 6, 7, 10, 11, 12, 13, 15, 16, 18 (numbered from current order)

  → 1.51.4 (Right canvas + chip nav + phase sections):
     - Right canvas section, Canvas Components section
     - ACs: 2, 3, 4, 5, 8, 9, 14, 17, 19, 20

  → Stays in parent only (archival):
     - Original "Why here" rationale, Supabase callout, the original unsplit AC list

Confirm allocation, edit, or cancel?
```

Only after the user confirms allocation, write the children:

1. **Children:** create one new file per child at `documentation/stories/<parent_id>.<n>.md`. Each child gets:
   - Frontmatter with `parent: <parent_id>`, fresh `depends_on` (often `[<parent_id>.<n-1>]` for sequential children + parent's original deps for the first child), and empty `depended_on_by`.
   - The allocated prose, ACs, and components from the confirmed allocation.
   - Initial `status: DRAFT`.

2. **Parent:** prepend a visible split block immediately after the frontmatter:
   ```markdown
   > **Split on 2026-04-28** into:
   > - [1.51.1 — Shared widget extraction](./1.51.1.md)
   > - [1.51.2 — ViewModel data-model migration](./1.51.2.md)
   > - [1.51.3 — Two-pane layout + structural panel](./1.51.3.md)
   > - [1.51.4 — Right canvas + chip nav + phase sections](./1.51.4.md)
   >
   > This story is closed to further refinement. Original prose retained below for archival; refer to the children for the live specification.
   ```
3. Update parent frontmatter: `status: SPLIT`, `children: [1.51.1, 1.51.2, 1.51.3, 1.51.4]`.
4. Append a "Split rationale" entry to the parent's `## Refinement log`.

The parent's original prose, ACs, and refinement log all remain in place. Nothing is deleted.

### Offer to refine children in the same session

After children are written, ask the user:

```
Children created. Refine them now in this session, or stop here?
  [1] Refine 1.51.1 next (recommended — keeps context warm)
  [2] Refine all children sequentially (1.51.1 → 1.51.2 → …)
  [3] Stop. User will re-invoke /refine per child later.
```

If the user picks (1) or (2), recurse: invoke this skill's flow on the chosen child file, starting from Step 1. Skip Step 2's grounding for repeated claims that were already verified for the parent in this session — pass the existing grounding table to the child as a known-good baseline (still re-ground anything new the child introduces).

If the user picks (3), proceed to Step 9 with the parent's verdict.

---

## Step 8 — Update the index

Maintain `documentation/stories/README.md`. If it does not exist, create it with this skeleton:

```markdown
# Stories Index

Per-story files for the Ocelot roadmap. Each story is one Markdown file. This index is auto-maintained by the `/refine` skill.

| ID | Title | Status | Parent | Children | Depends on | Depended on by | File |
|---|---|---|---|---|---|---|---|
```

For each refined story (parent and children if split), insert or update its row:

- `Status` reflects current frontmatter status.
- Cross-references are clickable relative links (e.g. `[1.51](./1.51.md)`).
- Sort rows by ID using natural numeric sort (1.5, 1.51, 1.51.1, 1.51.2, 1.52, 1.6 — not lexicographic).
- Preserve any narrative content above or below the table that the user has added by hand.

---

## Step 9 — Set final status and emit DoR verdict

Final status, written to frontmatter:

| Verdict | Condition | Frontmatter status |
|---|---|---|
| **READY** | All INVEST checks pass; no open spikes; no contradicted-and-unresolved grounding | `REFINED` |
| **NEEDS-SPLIT** | INVEST-S fails; user did not confirm split (or deferred) | `REFINING` |
| **BLOCKED** | One or more open spikes present | `BLOCKED` |
| **SPLIT** | Story was split this pass | `SPLIT` |

Set `refined_at` to today's date in ISO format.

Then output a single user-facing block:

```
=== Refinement complete: <story-id> ===

Verdict: <READY | NEEDS-SPLIT | BLOCKED | SPLIT>

Story: documentation/stories/<id>.md
Index: documentation/stories/README.md
<if split: list child files>
<if blocked: list open spikes by name>

Destructive changes this pass: <count>
Append-only log entries: 1
Open questions remaining: <count, if not READY>

Next action:
  - READY: ready to enter the implementation pipeline (e.g. /cycle).
  - NEEDS-SPLIT: re-run /refine and confirm the split, or restructure manually.
  - BLOCKED: resolve open spikes; re-run /refine when answers exist.
  - SPLIT: re-run /refine on each child to take it to READY.
```

Stop after this output. Do not auto-loop on children, do not auto-invoke other skills, do not commit. The user drives the next move.

---

## Notes for the agent

- Treat the story file as canonical. After every Step 4 batch, the file is the source of truth for in-progress refinement state.
- Resumability: on re-invocation with `status: REFINING`, read `## Open questions` (active queue) and the latest `## Refinement log` entry. Do not re-ask checked items unless the user requests a fresh pass.
- Never modify ROADMAP.md. The user migrates stories out of ROADMAP.md by hand.
- Never read or modify generated files (`*.g.dart`).
- When in doubt about destructive vs. clarifying: if the original prose is no longer recoverable from the result, it is destructive and must be logged.
- Token efficiency: all greps and code reads go through the haiku Explore subagent in Step 2. The main thread should not run grep/Read against `lib/` directly.
