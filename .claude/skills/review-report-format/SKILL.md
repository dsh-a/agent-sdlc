---
name: review-report-format
description: Output structure for the review agent's report — section order, severity buckets, finding format, verdict taxonomy. Single source of truth for review report shape; consumed by review.md and any tooling that parses review reports.
disable-model-invocation: true
---

# Review Report Format

The `review` agent appends sections to its report as each step completes (Step 0 opens the file with `Verdict: IN PROGRESS`; sections append; Step 7 finalizes the verdict). This skill defines the section structure and finding format.

---

## Section order

| Section | Step | Content |
|---|---|---|
| Architecture | 2 | Layer-boundary violations (or "Clean — no layer violations") |
| Convention Compliance | 3 | Issues grouped by type (member order, naming, style, pattern) |
| Code Quality | 4 | Complexity / duplication / error handling / security findings |
| Test Coverage | 5 | Missing or insufficient tests (lighter than verify's audit) |
| Auto-Fixed Issues | 6 | Critical/warning issues that were fixed, with file + line |
| Summary | 7 | Counts + verdict |

---

## Severity buckets

- **Critical** — blocks merge. Layer-boundary violations on hot paths, missing error handling on system boundaries, security issues, broken contracts.
- **Warning** — should fix. Convention drift, complexity above thresholds, missing tests on changed behaviors.
- **Suggestion** — nice to have. Documentation gaps, minor refactor opportunities, style nits beyond conventions.

The agent **auto-fixes** Critical and Warning findings; Suggestions are listed but not applied.

---

## Finding format

For each remaining (unfixed) finding in any section:

```
- file: <path:line>
  issue: <one-sentence description>
  fix: <suggested change>
  severity: critical | warning | suggestion
```

For findings fixed in Step 6, the `Auto-Fixed Issues` section lists them with `fixed: yes` and the same shape.

---

## Summary section

```
- Critical issues (must fix): [n fixed, n remaining]
- Warnings (should fix): [n fixed, n remaining]
- Suggestions (nice to have): [n]
- Verdict: APPROVE | REQUEST CHANGES | NEEDS DISCUSSION
```

Verdict rules:
- **APPROVE** — 0 critical remaining and 0 warnings remaining.
- **REQUEST CHANGES** — any critical remaining.
- **NEEDS DISCUSSION** — warnings remaining but no critical; reviewer wants user judgement.

Finalize by editing the report header `Verdict: IN PROGRESS` to the chosen verdict.

---

## Report header

```yaml
Branch: [branch or PR]
Reviewed: [YYYY-MM-DD]
Verdict: IN PROGRESS  # finalized in Step 7
```
