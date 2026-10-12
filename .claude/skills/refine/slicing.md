# Slicing a story for a stack

A `full` story ships as a stack of pull requests, one per slice, built bottom-up by one `/cycle`.
Cut the slices here, while the grounding table is in hand.

## A slice

- **Green at its boundary.** With this slice and every slice below it merged, the suite passes.
- **Tightly located.** Its diff sits in one area: a layer, a component, a migration.
- **Carries its own tests.** The tests for a slice's code are in that slice.
- **Depends downward only.** Code a slice calls is in that slice or a lower one.

A slice need not be demonstrable alone. That is a split's bar (Step 7); a slice only has to be
reviewable alone.

## Choosing the cut

Cut where grounding shows a boundary: a layer the change crosses, a shared component extracted
before its consumers, a migration ahead of the code that reads it. Order the slices so each one
builds on the last. Two to four slices fit most stories.

Propose the cut and take a confirmation, as for a split:

```
Proposed slices for #412:
  1 — Restriction model and repository   lib/domain/health/, lib/data/health/   AC 1, 2, 5
  2 — Restrictions section on the screen  lib/ui/health/                         AC 3, 4
Confirm, adjust, or keep as one slice?
```

## Writing it

Add `## Slices` to the issue body after `## Acceptance Criteria`. One numbered line per slice,
bottom of the stack first: title, area, ACs by their ordinal in `## Acceptance Criteria`.

```
## Slices

1. Restriction model and repository — `lib/domain/health/`, `lib/data/health/` — AC 1, 2, 5
2. Restrictions section on the health screen — `lib/ui/health/` — AC 3, 4
```

`AC 2-4`, `all ACs` and `AC none` are accepted. Every AC belongs to exactly one slice: the lowest
slice whose code satisfies it.

A story with no real boundary keeps one slice and says why:

```
## Slices

1. Whole story — `lib/ui/settings/` — all ACs

Single slice: one widget and its test; any cut leaves a slice that does not compile.
```

## A story already refined

A `REFINED` `full` story with no `## Slices` takes a slices-only pass. `story.py load` names this
case. Offer it at Step 1 alongside a full pass.

1. Step 1 in full: restate, take the confirmation, set `Refinement` to `REFINING`.
2. Propose the cut, take the confirmation, write `## Slices`, run `story.py slices <n>`.
3. Leave probes, grounding and the question queue alone; the last pass's results stand. Compare
   the commit the body's grounding cites with the integration branch. When it is behind, say so
   and offer a full pass.
4. Step 8 in full: the complete restatement, the sign-off, then `REFINED`. In the restatement,
   give the last pass's `Probes:` line and the commit it was grounded at.
5. Log the pass as slices-only, with the cut and the reason for it.

A contradiction or an unclear AC found while cutting ends the slices-only pass: continue as a
full pass from Step 2.

## Checking it

```sh
python3 .claude/skills/refine/story.py slices <n>
```

`verdict=anomalous` names each AC that is unplaced, placed twice, or out of range. Re-run it after
any edit that adds, removes or reorders an AC, because slices cite ACs by position. `story.py dor`
runs the same check for a `full` story.
