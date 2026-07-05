---
name: minimalism-review
description: Over-engineering review lens for the review agent. Scans a diff for what to delete — reinvented stdlib, needless dependencies, speculative abstractions, dead flexibility — with a fixed tag vocabulary and a net-lines score. Complements correctness/security review; it only hunts complexity. Loaded by the review agent as a sub-step of Code quality.
disable-model-invocation: true
---

# Minimalism Review

Review the diff for unnecessary complexity only. The diff's best outcome is getting shorter. One line per finding: location, what to cut, what replaces it.

This is the review-time mirror of the `minimalism` ladder the implementers build under. Same instinct, opposite direction: the ladder stops code being written; this catches what slipped through.

---

## Format

`<file>:L<line>: <tag> <what>. <replacement>.`

Tags:

- `delete:` dead code, unused flexibility, speculative feature. Replacement: nothing.
- `stdlib:` hand-rolled thing Dart's stdlib / `collection` ships. Name the function.
- `native:` a dependency or hand-rolled code doing what Flutter already does. Name the widget/feature.
- `yagni:` abstraction with one implementation, config nobody sets, layer with one caller.
- `shrink:` same logic, fewer lines. Show the shorter form.

## Hunt

- Packages added to `pubspec.yaml` (or already there) doing what stdlib/Flutter ships.
- Single-implementation interfaces and abstract classes that aren't a required layer seam (`flutter-conventions` mandates interfaces at layer boundaries — those are *not* findings; an `AbstractThing` with one impl and one caller inside a layer *is*).
- Factories with one product, wrappers that only delegate, files exporting one thing.
- Dead flags, unread config, hand-rolled loops that are one `collection` call.
- `copyWith` re-implemented by hand where the generated/existing one exists.

## Examples

✅ `lib/data/email.dart:L12-38: stdlib: 27-line validator class. Regex + the confirmation mail is the real validation.`
✅ `pubspec.yaml:L44: native: intl added for one date format. DateFormat is already a dep; or MaterialLocalizations.`
✅ `lib/domain/repo.dart:L88: yagni: AbstractSyncRepository, one implementation, one caller. Inline until a second exists.`
✅ `lib/ui/list/list_view.dart:L52-71: delete: manual scroll-retry around an idempotent local read. Nothing replaces it.`
✅ `lib/utils/map.dart:L30-44: shrink: loop builds a map. Map.fromIterables(keys, values), 1 line.`

## Scoring

End with the only metric that matters: `net: -<N> lines possible.` Nothing to cut: `Lean already. Ship.` and stop.

## Boundaries

- Scope is over-engineering and complexity **only**. Correctness bugs, security holes, schema drift, and performance are out of scope here — they belong to review Steps 2–4, not this lens. Do not double-report them.
- A required layer-boundary interface, an AC-mandated feature, and the pipeline's required tests are never findings. A single smoke test or self-check is the minimum, not bloat.
- This lens **lists**; it does not decide verdict. Feed findings into the review report's Code quality section per `review-report-format` (a `shrink:`/`yagni:` finding is a Suggestion unless it also trips a real convention rule, which the other steps own). The review agent's auto-fix policy governs what gets applied.
