# Output templates

Two blocks whose shape matters and whose prose does not need to sit in `SKILL.md`. `cat` the one
you need; the rules that explain them are in `SKILL.md` Step 5 and Step 8.

## The refinement-log comment (Step 5)

One per pass, posted at the end of the pass, never edited afterwards. The `**Probes:**` line is
pasted from `probes.py coverage` — a line you write by hand is a claim, a line the script printed
is a count.

```markdown
## Refinement log

### 2026-04-28 — Pass 1

**Probes:** inherited-claim 9/9 · measured-number 7/7 · mechanism-exists 13/13 ·
ac-strict 19/19 · deferred-number 1/1 · concrete-deferral 3/3 · named-edge 10/10 ·
profile-impact unavailable (no `product/customer-profiles.md`)

**Grounding:**
- VERIFIED: `OrderSearchPanel` at `lib/ui/orders/views/order_search_panel.dart`
- CONTRADICTED: story claimed `_orderLines` is a `Map<String, OrderLine>`; actual type is
  `Map<String, List<OrderLine>>`. User confirmed the prose was outdated; rewrote.

**Mechanism proven** (Step 2b; omit when the story asserts none):
- `flutter test --tags 'story:488'` → `Invalid tag name…` exit 1, Flutter 3.44.4. Rules out the
  inherited `story:<issue>` taxonomy; corrected here and in #415, #416.
  Probe ran in `/tmp/tagprobe`, outside the repo; **deleted.**

**Questions answered:**
- Q (Scope): What does the AI `[⚡]` button look like when out of scope? → Hidden until 1.8.
- Q (Behavior): Cross-phase drag allowed? → Yes, including from UNPHASED. Added AC.

**Destructive changes to story:** <each one, in a line>

**Open spikes raised:** see `## Open spikes` (1 added).

**Self-corrections this pass:** 4 probe failures, 0 content errors. A `Chip(` sweep counted
`ChipThemeData(` and a commented line; the story's figure was right.

**Contradictions that did not survive checking:** agent reported "five stories' worth of churn"
as contradicted, citing 17 stories — the body cites D-8, which names exactly five. It quoted D-8
while contradicting it. **No change made.**

**DoR verdict at end of pass:** NEEDS-SPIKE

**Sign-off:** n/a — verdict is not READY. (When READY: `approved <date>` or `changes requested: <what>`.)
```

The last two sections are required when they apply and are different facts: **self-corrections**
separate instrument failure from content failure, and **contradictions that did not survive**
record agent findings you examined and rejected.

## The closing verdict block (Step 8)

Printed once, after sign-off and after the board is written. Then stop.

```
=== Refinement complete: #<n> ===

Verdict: <READY | NEEDS-SPLIT | BLOCKED | SPLIT>

Issue: <url>
<if split: child issue numbers>
<if blocked: open spikes by name>

Depth: <full | lean | hotfix>   (READY only; "board has no Depth field" if absent)

Destructive changes to the issue body: <count>
Signed off by user: <yes | n/a — verdict is not READY>
Refinement-log comments posted: 1
Open questions remaining: <count, if not READY>

Next action:
  - READY: ready to enter the implementation pipeline (e.g. /cycle).
  - NEEDS-SPLIT: re-run /refine and confirm the split, or restructure manually.
  - BLOCKED: resolve open spikes; re-run /refine when answers exist.
  - SPLIT: re-run /refine on each child to take it to READY.
```
