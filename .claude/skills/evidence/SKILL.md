---
name: evidence
description: How to gather evidence you can stake a claim on — search-method rules for a grep-running subagent, the discipline for absence claims and citations, and the `evidence.py` verbs that replace hand-written verification scaffolding. Single source of truth for instrumentation discipline.
disable-model-invocation: true
---

# Evidence

An agent refining eight stories across two days logged roughly **ten instrumentation
errors against zero wrong claims about the codebase**. Its reasoning from evidence held
up; its gathering of evidence did not. Two of the ten were one step from being filed as
GitHub issues — including a bug report asserting that "every `session_set` write has been
rejected" for want of an INSERT policy, concluded from reading **1 of 26** migration
files. The policy had been added two months earlier by a migration it had not read, whose
sibling file contains the comment *"this comment exists so a future reader of this
migration does not conclude it was missed."*

That is the gap this skill fills. Every rule here is about **how a fact was obtained**,
not about what the fact was. `project-conventions` owns what the code should look like;
`ac-audit-rubric` owns whether an AC is covered; this owns whether you actually know.

---

## The discipline

- **An absence claim carries its corpus.** Not just its result. "X does not exist" is
  meaningless without which paths were searched, how many, and why that set. One of 26
  migrations read as "the schema" is the expensive version of this; a subagent prompt that
  scoped a search to a single file and returned `NOT-FOUND` for a symbol existing **17
  times** in the repo is the cheap version. Both verdicts were artifacts of the probe.
- **Could-not-determine is never absent.** A path that does not exist, a file that would
  not decode, a command that failed — each is a third outcome, and collapsing it into
  "nothing found" is how six absence claims were made over a directory grep had errored on.
- **Grep for the fact, never for the phrasing you remember.** A correction took three
  attempts because each pass enumerated the phrasings its author recalled writing rather
  than searching for the underlying fact. The remembered list had four entries; the search
  found six. Later, the same shape: a gate flagged **one** stale claim and auditing every
  mention of the concept found **three**, the worst of them a table row an implementer
  would read to learn what a guard requires. Enumerating your own phrasings finds a subset
  by construction.
- **Read the bytes; never retype them.** Five guarded edits aborted in one session, every
  one because an anchor string was written from recall of prose authored minutes earlier,
  usually with a line wrap guessed wrong. The abort was the guard working. The retype was
  avoidable.
- **Judge paragraphs, not lines.** A qualifier and the phrase it qualifies routinely land
  on different lines. Four gate failures came from exactly that, plus a case-sensitivity
  variant (`'under e2e/'` against `Under e2e/`).
- **A gate failing is evidence.** After seven instrumentation failures in one session, an
  agent opened its response to a malformed-table report by calling the gate "almost
  certainly" wrong about its own cell counting. The gate was right: the file held literal
  `\|\|` pairs — six raw pipes against a four-pipe header — which rendered as a five-column
  row inside a three-column table. Visible garbage, failing silently, exactly the class of
  defect the gate existed to catch. **That your probes have usually been the culprit is not
  a reason to assume it this time.** Disprove a gate with a fresh read of the artifact,
  never with recollection.
- **A probe that disagrees with a settled figure is the likelier suspect.** The corollary to
  the rule above, and it caught two near-misses in one cycle: a predicate measured 0 weight-only
  rows where 18 exist, and a split-on-commas check failed two correct fixtures. Both times the
  figure was right and the probe was new. A gate failing is evidence; your own ad-hoc
  measurement disagreeing with a number someone already established is a reason to re-read the
  probe first.
- **A conclusion and its citation fail independently.** See § Checking a subagent's
  citations.

---

## Method rules for a search subagent

Four of the failure classes above are one bug four times: **grep was reached through a
shell, and a shell is a lossy channel for both the pattern and the verdict.**

A subagent that greps needs these rules in its prompt, because it cannot be given this
file to read reliably and, when it is a built-in harness agent such as `Explore`, it has
no body the framework can edit. **Paste the block below verbatim** into any spawn prompt
whose work is searching. Do not paraphrase it — the specifics are the content.

```
Search method — these are not style preferences, each one has produced a false finding:

1. Quote every glob: `--include="*.md"`, never bare. zsh expands an unquoted glob before
   grep sees it, and with no match in the current directory it aborts the command — which
   inside an && chain reads as "no results" rather than "did not run".
2. Never pipe grep when its exit status is the signal. `grep ... | head` reports head's
   status, which is always 0.
3. `grep -c` counts matching LINES, not occurrences. Occurrences are `grep -o PAT | wc -l`.
4. Before any absence claim: confirm each path exists, and distinguish grep's exit 1
   (no match) from exit 2 (error). An error read as "no match" is a false absence.
5. State your corpus with every absence claim — which paths, how many files, and why that
   set. A result over a subset is a result about the subset, and must say so.
6. Quote real bytes. Every citation must be text you read in this session, from the file
   you name. Do not reconstruct a quote from memory, and do not attribute a line to one
   source because it sat next to that source in your notes.
7. Judge paragraphs, not lines. A qualifier may wrap onto a different line than the phrase
   it qualifies, so a line-scoped rule sees an unqualified claim that is not there.
8. Never split CSV/TSV rows on a raw separator. A quoted field contains them — `"IAF - Legs,
   Abs"` shifted every later column and failed two correct fixtures. Use a real parser.
9. Numbers in data files carry their formatting. A predicate testing membership in `('','0')`
   measured 0 weight-only rows where 18 exist, because the column is always written `0.0`.
   Look at the actual bytes of a column before writing a predicate over it.
10. To read part of a file, use `grep -n` plus the Read tool — not `sed -n '1,200p'`. Both read,
    but `sed` reads as a write to anyone scanning the command, and a reviewer did read it that
    way: one `sed -n '…p'` on a skill file sat as an unanswered permission ask for 24h46m.
    An unambiguous command is worth more than a terse one.
```

The block costs roughly 250 tokens per spawn and is **pasted, not autoloaded** — nothing
should name `evidence` in `autoloadSkills`, which would charge every spawn for it and
change the context budget.

### When the block is unreachable

Per `autonomous-agent` § Skill resolution, never apply a named skill from memory. The right
exit differs by caller:

| Caller | Fallback |
|---|---|
| An unattended pipeline agent (`/cycle`) | `contradiction-exit` with `trigger: skill-unreachable` and the paths tried |
| An interactive skill (`/refine`) | Tell the user the block is unreachable, say that delegated grounding would be unverified, and **do the grounding on the main thread instead** |

A structured bail-out in a dialogue session is worse than the honest sentence, and a
half-remembered version of the block is worse than either.

---

## Checking a subagent's citations

A grounding subagent once attributed a sentence to a GitHub issue's body when it had
actually read it from a source-code comment one row earlier **in its own report**. The
phrase appears **0 times** in that issue. The conclusion survived on other evidence — which
is the point: the citation was fabricated by conflation while the reasoning was sound, so
checking the conclusion would never have caught it.

**Check citations separately from conclusions, on receipt, before any row is used.** Not as
a later pass — a later pass is a pass that gets skipped, and a citation is cheapest to check
while the report is still in context.

- **Re-check every citation that will leave the session** — anything bound for an issue
  body, a PR body, a bug report, a run report, or a sign-off restatement. Both near-misses
  were about-to-be-published findings.
- **Spot-check two others**, the most load-bearing rows. Full re-checking would refund the
  delegation's savings.
- **Tooling:** `evidence.py cite --phrase - --source -`. It normalises whitespace and case,
  so a quote that wrapped differently in the source still matches.

**How it fails matters.** `hits=0` strikes the *citation*; the claim reverts to
**unverified**, not false. Re-ground it from a source you read directly, or convert it into
a question. Never silently keep the claim with the bad citation, and never discard the claim
because the citation was bad — a rule that deleted claims would teach the agent to skip the
check to protect its conclusions.

---

## The tool

`.claude/skills/evidence/evidence.py` replaces the verification scaffolding that was
hand-written **roughly fifteen times in one session**. **No verb invokes a shell, and none
invokes grep** — patterns are Python `re`, corpora are resolved with `pathlib`. The four
shell-channel failure classes are therefore unexpressible rather than merely discouraged.

| Verb | Answers |
|---|---|
| `absence` | is a pattern present in an explicitly named corpus |
| `anchor` | what are the exact bytes of this region, to paste into an edit |
| `guarded-edit` | apply these edits, but only if every anchor is unique |
| `tables` | does every Markdown table row's cell count match its header's |
| `cite` | does this quoted phrase appear in the source it is credited to |
| `round-trip` | is what I pushed what the destination now returns |
| `enumerate` | what happened to each item between these two texts |

```sh
python3 .claude/skills/evidence/evidence.py absence --pattern 'INSERT POLICY' supabase/migrations
ABSENCE verdict=present pattern=INSERT POLICY unit=paragraph corpus=26/26 files=26 hits=1 occurrences=2
```

### Exit codes

| | |
|---|---|
| `0` | determinate — the claim holds |
| `1` | determinate — the claim does not hold |
| `2` | bad usage |
| `3` | **could not determine** |

`1` carries this repo's "refused or no hits" meaning, as in `symbol-refs.py` and
`pitfalls.py` — **not grep's**. For `absence`, `1` means the pattern is *present*, the
inverse of grep's `1`. So `verdict=` on the first line of stdout is the primary channel and
the exit code the branchable secondary: a caller reading only the status with grep habits
gets the right answer backwards, and a caller who pipes to `head` still sees the word.

Three invariants, each one a failure class:

- **A corpus that did not fully resolve exits 3**, even when the part that did resolve had
  no hits. Every unresolved path is printed on an `unresolved:` line. Nothing collapses into
  `absent`.
- **An empty corpus exits 2.** "State your corpus" is enforced by argparse, not by this
  sentence.
- **Nothing accepts an expected total.** Predicted item counts were wrong three times while
  the content was right, so `enumerate` reports each item's disposition and has no count to
  check against.

### Notes per verb

- `absence` defaults to `--unit paragraph`, because a default that must be remembered is the
  bug. `--allowed-context REGEX` excuses a unit that also matches a qualifier, and every
  excused unit is printed with its line range — a paragraph-scoped excuse is the one place
  this could be too generous, so the caller gets something to eyeball rather than a bare
  verdict. Matching is case-insensitive unless `--case-sensitive`. `--suffix .md` narrows a
  directory walk and is never handed to a shell.
- `anchor` prints bytes with `occurrences=1` proved at print time. Use it before
  `guarded-edit`, not after an abort.
- `guarded-edit` **checks by default**; `--apply` writes. Every anchor's count is taken
  against the original bytes before any substitution, so a batch cannot half-apply.
- `tables` reports two fault kinds. `fault=cells` is an unambiguous structural mismatch.
  `fault=pipe-run` is the observed defect's shape — a run of two or more consecutive
  escaped pipes whose raw pipe count disagrees with the header. A single `\|` in a cell and
  a pipe inside a code span are idiomatic and stay clean, deliberately: a gate that cries
  wolf is a gate whose failures get dismissed.
- `round-trip` takes `--remote-cmd` so the script knows nothing about `gh`. A failed or
  empty read-back exits **3**, never `identical`.
- `enumerate` labels each item `kept` / `replaced` / `added` / `deleted`. Repeat `--after`
  for a split: every before-item must land in exactly one child, and `unplaced` /
  `duplicated` are reported per item.

### Who runs it

The **main thread** of a skill, which holds the Bash grant
(`.claude/settings.json` § permissions). A subagent gets the § Method rules block in its
prompt instead — the actor that would need a per-script grant is often a built-in harness
agent whose frontmatter the framework does not own, and omp cannot express per-script scope
at all (see `test-preflight`).
