---
name: harness-intake
description: Turn the harness findings already written in run reports into a ranked, deduplicated backlog of GitHub issues on the framework repo, with an occurrence count per finding. Repo-maintenance workflow — private-only, never part of the deployed pipeline. Run from the framework checkout, on command.
disable-model-invocation: true
---

# Harness Intake

Every cycle writes a `## Harness findings` section. Nothing has ever read them **across** cycles,
and that is the whole defect this skill exists to fix.

Measured over myapp's archived run reports:

| | |
|---|---|
| Run reports | **114** |
| With a findings section | **62** |
| Findings in them | **226** |
| Distinct normalised titles | **226** — not one exact repeat |
| A base-mismatch fault appears in | **35** reports |
| Severities it was given | **P0 ×3 · P1 ×1 · P2 ×3 · P3 ×1** |

The last row is the finding about the findings. The worktree-base bug was filed **P0 on
2026-08-24**, was still live six weeks later, and in between was rated across the entire scale by
different cycles. `harness-findings` says a P0 is worth acting on immediately;
`pipeline-metrics-rubric` says three occurrences is a defect rather than an incident. **Neither has
ever fired on it, because nothing computes an occurrence count.**

Severity decided inside one cycle is noise. **Recurrence is the signal, and only a framework-side
pass can see it.**

---

## What this is not

- **Not automatic.** Nothing here runs during a cycle. A cycle writes its report and stops; staging
  costs zero extra tokens because the report is the staging. This skill runs when you type it.
- **Not a fixer.** It produces a ranked backlog. `/self-improve` owns analysis and applying
  framework changes.
- **Not runnable from a project.** `deploy.sh` links every tracked skill directory, so this one
  appears in every deployment. Run it from the framework checkout only: inside a project `gh`
  resolves to the *product* repo, and filing framework faults there is the wrong tracker.

### The boundary with `/self-improve`

| | `/harness-intake` | `/self-improve` |
|---|---|---|
| Reads | `## Harness findings` sections; the framework issue list | the 3E metrics sections; the issue list |
| Produces | issues + a ranked queue | `REC-NNN` recommendations, and edits to agent/skill files |
| Decides | identity, recurrence, severity, state | what to change, and whether to change it |
| Never | proposes or applies a fix | re-derives recurrence from reports |

Worth holding onto, because it makes the split memorable: `self-improve` files **product** bugs
from `## Bugs discovered` into the project's tracker; intake files **process** faults from
`## Harness findings` into the framework's. Disjoint sections, disjoint repos, same mechanism.

---

## Step 1 — Extract

`findings-extract.py` does the mechanical half. It takes report files or directories, and a
standalone `findings-*.md` is recognised by filename as a whole-document section.

```sh
python3 .claude/skills/harness-intake/findings-extract.py \
  ~/dev/myapp-docs/reports/myapp docs/internal --json
```

```
FINDINGS reports=114 findings=226 p0=5 p1=35 p2=62 p3=124 clean=0 unparsed=18
```

Read the header before anything else:

- **`unparsed=N` is not a footnote.** It means N reports have a findings section that yielded
  nothing — the exact failure `pitfalls.py` shipped with for months. Exit code **3**. The 18 in the
  corpus are cycles that wrote a numbered list instead of `### P[0-3] —` headings, and **one of them
  holds the worktree P0 in prose**. Skim those by hand; do not assume they are empty.
- **`clean=N`** counted the explicit `None — probes 1-12 checked, all clean.` sentence. That is a
  claim the probes were worked, and a different fact from a section that would not parse.
- `reports=N` is the corpus. An absence claim without it is meaningless (`evidence` § The
  discipline).

## Step 2 — Group, and let recurrence set severity

Titles never repeat, so **identity is not the title**. Group on:

1. **title-token overlap** after dropping stopwords and severity words — the six worktree findings
   share `worktree`, `isolation`, `base`, `forks`;
2. **the `artifacts` field**, which carries the path- and file-shaped tokens a finding names.
   `gate-report.py` appears in 16 findings, `aggregate-telemetry.py` in 12. Where artifacts are
   present they are the stronger signal; the worktree group has almost none, which is why both
   signals are needed.

**Group conservatively. Over-grouping is the worse error** — it hides a distinct P0 inside another
issue's history. When a match is uncertain, file separately and say so.

Then set severity by **max-ever, never downgrade**:

| Occurrences | Floor |
|---|---|
| 2 | at least P1 |
| 3+ | at least P0, and `harness:recurring` |

A finding arriving as P2 against an issue already at P0 stays P0, with a note that this cycle rated
it lower. The corpus shows the worktree bug being downgraded P0→P2 with no new information; an
automatic downgrade would have dropped it out of the queue again.

## Step 3 — File

Issues go on the **framework** repo. Resolve it explicitly and refuse anything else — this clone
has more than one remote, so `gh`'s default is not safe here:

```sh
REPO=$(git remote get-url origin | sed 's#.*[:/]\([^/]*/[^/]*\)\.git#\1#')
case "$REPO" in *agent-sdlc*) ;; *) echo "refusing: $REPO is not the framework" >&2; exit 1 ;; esac
```

**One list call, not one search per finding.** A per-title search finds nothing — all 226 titles are
unique — which is exactly how you end up with 226 issues:

```sh
gh issue list --repo "$REPO" --label harness-finding --state all --limit 1000 \
  --json number,title,state,labels,body
```

That call is also the watermark. **Keep no local state**: the ingested set is derivable from the
issues themselves, so there is no file to conflict on, go stale, or disagree with the tracker.

Labels, created once (`gh label create … || true`):

| Label | Meaning |
|---|---|
| `harness-finding` | the query key; every issue intake owns carries it |
| `harness:P0`…`harness:P3` | current **max-ever** severity, exactly one |
| `harness:recurring` | 3+ occurrences |
| `harness:regressed` | recurred after the issue was closed |

No per-project label: a finding recurring in two projects is one framework bug, and labelling by
project invites triaging it twice.

**Issue body** — the first occurrence's title verbatim, never rewritten (later wordings are
aliases), and an occurrences table rather than a comment per occurrence. GitHub shows a comment
count, not an occurrence count, and six comments is something to read rather than a number to sort
on. Close with a machine-readable block so the next run can find it:

```markdown
**Severity P0** · 6 occurrences · first 2026-08-24 · last 2026-10-03 · projects: myapp

<the first occurrence's body>

**Suggested fix:** <the latest occurrence's fix>

## Occurrences

| Date | Severity | Project / cycle | Report | Title as filed |
|---|---|---|---|---|

---
_Machine state for `/harness-intake` — do not edit below this line._
<!-- harness-intake:v1
{"v":1,"severity_max":"P0","first_seen":"...","last_seen":"...",
 "occurrences":[{"report":"...","date":"...","severity":"..."}],"aliases":["..."]}
-->
```

Human-facing words all live above the `---`, so retitling or rewriting an issue cannot break the
link. **A `harness-finding` issue whose marker is missing or will not parse is an error** — report
it and stop; never respond by filing a duplicate.

**`--dry-run` first, always.** Filing on a shared repo is outward-facing, and the default for
outward-facing operations in this framework is dry (`prune-analyzer-baselines.py`). Print the plan,
then apply.

**Intake never closes an issue.** A finding that stops recurring may just mean nobody ran that
probe. It does **reopen**: a new occurrence against a closed issue gets `harness:regressed`, one
comment naming the new report, and the top of the queue — a fix that did not hold is the most
valuable signal this produces.

## Step 4 — The queue

Rank `(max-ever severity, −occurrences, −age)`. Lexicographic, not a composite score: when a score
puts a P1 above a P0 the list stops being trusted, and an untrusted list costs more than none.
**Ten rows and a tail count.**

```
HARNESS-INTAKE repo=dsh-a/agent-sdlc-private reports=114 new=3 recurred=9 reopened=0 issues=12

! #7  P0 ×6  2026-08-24 → 2026-10-03 (40d)  worktree isolation forks from the wrong base
      pass the session branch to `git worktree add`; the base resolves to `main`
  #9  P1 ×2  2026-09-12 → 2026-10-03 (21d)  `analyzer_baseline` drift cannot work as specified
```

Print the **fix line** under each row — it is what tells you whether this is a ten-minute job — and
the **age span**, which is the argument for acting now. And print `×N`, because that number has
never existed before.

### First run: ladder by severity

226 findings filed at once buries the queue. Do three passes, reviewing each dry-run:

1. `--severity P0` → 5 findings, ~2–3 issues. **This pass alone delivers the point**: the worktree
   bug appears carrying `×5`, `harness:recurring`, and a 40-day age.
2. `--severity P1` → +35.
3. `--severity P2` → +62.

P3s stay unfiled — 124 of 226 are P3, mostly one-off friction. Nothing is lost: the reports are the
staging, so any P3 is re-derivable at any time with `--severity P3`.

Then backfill `docs/internal/findings-*.md`. This is **not optional**: the 2026-08-24 P0 exists
nowhere else — that cycle's run report has no findings section at all.
