---
name: pr-body-format
description: Output structure for the pull-request body written at Phase 4B — section order, source map, the reviewer's reading path, and the honesty rules for gaps and deviations. Single source of truth for PR body shape; consumed by the cycle skill's step 8 and any tooling that generates a PR description.
disable-model-invocation: true
---

# PR Body Format

The cycle's step 8 writes a PR body to `cycle_reports/pr-body-[feature-name]-[YYYY-MM-DD].md` and creates
the PR with `gh pr create --body-file`. This skill defines that file's shape.

---

## Audience — read this before writing anything

The **cycle run report** and the **PR body** draw on the same artifacts and share almost no
content. They answer different questions for different readers.

| | Cycle run report | PR body |
|---|---|---|
| Reader | the maintainer, and `/self-improve` | a human reviewer; archaeology in six months |
| Answers | what the pipeline cost getting here | what changed, why, and where to look |
| Lifetime | archived, then summarized into `agent_metrics.md` | permanent, in the git record |

**Do not paste the run report into the PR.** Link it in one line inside the collapsed
`Pipeline detail` block. Agent audits, token estimates, model escalations, supervisor uptime
and harness findings are pipeline telemetry — they belong in the report and nowhere near a
reviewer's screen.

---

## Source map

Every section comes from an artifact that already exists on disk at step 8. Nothing here
requires new collection, and nothing should be invented to fill a section.

| Section | Sourced from |
|---|---|
| Opening paragraph | PRD problem statement / goal (lean mode: the AC summary in cycle state) |
| `Closes #n` | the story issue the cycle originated from |
| What changed | task file parent tasks + `git log [base]..HEAD` |
| Read in this order | `git diff --stat [base]...HEAD` + the files named in the review report |
| Verification | verify report verdict table, review report Summary, test counts, analyzer drift |
| Known gaps | cycle state `## Deviations` + verify PARTIAL/NO IMPL criteria |
| Pipeline detail | run report path, cycle state `## Rescues` count |

If a source is absent (verify skipped, no story issue, lean mode with no PRD), omit that
section entirely. Do not emit a heading with "n/a" under it.

---

## Section order

```markdown
[One paragraph: the problem this solves and why now. Prose, not bullets. From the PRD's
problem statement, rewritten for someone who has not read the PRD.]

Closes #[story issue]

## What changed
- [parent task 1.0 restated as an outcome, one line]
- [parent task 2.0 …]

## Read in this order
1. `path/to/file.dart` — [why this file matters and what to check in it]
2. `path/to/other.dart` — [ditto]
3. `test/path/to/file_test.dart` — [what the new cases cover]
<details><summary>[n] more files — [one-phrase category, e.g. codegen, DI wiring, imports]</summary>

[flat list of the remaining paths]

</details>

## Verification
| | |
|---|---|
| AC coverage | [n]/[n] PASS · [n] NO IMPL |
| Review | [APPROVE / REQUEST CHANGES / NEEDS DISCUSSION] · [n] critical, [n] suggestions remaining |
| Tests | [n] added, [n] failing |
| Analyzer | [clean vs. baseline / n new warnings / not tracked] |

## Known gaps / accepted deviations
- [AC id or area]: [what was implemented instead] — [why]

<details><summary>Pipeline detail</summary>

Run report: `agent_tasks/reports/report-prd-[feature]-[date].md`
Rescues: [n] ([types], or "none")

</details>
```

---

## Read in this order — the section that earns the PR

This is the highest-value part of the body and the part a human author almost never writes.
A reviewer facing a forty-file cycle branch skims it; a reviewer handed an ordered path
reads it.

Rules:

- **Rank by what the reviewer must understand, not by path or by diff size.** The file
  holding the actual behaviour change is first even if it is a six-line diff.
- **Three to five entries above the fold.** Everything else goes in the `<details>` block,
  grouped under one phrase.
- **Each line says what to check**, not what changed — the diff already says what changed.
  "retry policy moved here from the facade; check the backoff bounds" beats "updated retry
  logic".
- **Never list a generated file above the fold.** `.g.dart`, `.freezed.dart`, lockfiles and
  DI registration go in the collapsed block, always.

---

## Known gaps — the honesty rules

The pipeline records deviations and accepted gaps at the moment they happen. A human author
writing this PR by hand a day later would not remember them. Carrying them forward is the
point of generating the body from cycle artifacts, so:

- **Every entry in cycle state `## Deviations` appears here.** No exceptions, no summarizing
  several into one.
- **Every verify criterion that is not PASS appears here**, with its verdict.
- If the user explicitly accepted a gap at the 4B gate, say so and say it was accepted —
  not "minor" or "by design".
- If there are genuinely none, write `None.` and keep the heading. A reviewer reading `None.`
  learns something; a missing heading is ambiguous.

Never soften a `PARTIAL` or `REQUEST CHANGES` verdict in the Verification table to make the
PR look cleaner. The table is the reviewer's basis for how hard to look.

---

## Mechanics

1. Write the body to `cycle_reports/pr-body-[feature-name]-[YYYY-MM-DD].md`.
2. Create the PR with `--body-file`, never `--body`:

   ```sh
   gh pr create --base [pr_target] --title "[type]([scope]): [summary]" \
     --body-file cycle_reports/pr-body-[feature-name]-[YYYY-MM-DD].md
   ```

   The body contains tables, backticks and `<details>` tags. Inline `--body` with a heredoc
   will mangle at least one of them.
3. Because the body is a file, it is inspectable before the PR exists and regenerable after.
   When `pr_body_gate` is `true` (§ Cycle Options), show the rendered file and wait for the
   user before running `gh pr create` — same shape as Gate 1 and Gate 2.
4. On an update to an existing PR, rewrite the same file and
   `gh pr edit [n] --body-file [path]`. Do not append.
