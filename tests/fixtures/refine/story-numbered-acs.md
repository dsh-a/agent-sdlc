## Why this exists

A lean `/cycle` on #421 was stopped at grounding on 2026-09-13. The story wasn't ready to implement. Two open stories defined golden testing and contradicted each other — #421 (`matchesGoldenFile`, no new dependency) and #414 (`alchemist` as a dev dependency, per #249 D-5). One repo should not end up with two golden mechanisms.

**That reconciliation is done.** #421 and #414 were both closed `superseded:merged` on 2026-09-13, and #488 absorbed them as the single golden-testing story under #249.

> ### Pass 3 — 2026-10-03. The spike reported; this story is now a build, not a question.
>
> **#547 ran on 2026-10-02** and closed `completed`. Its verdict: **Arm A — `flutter_test` only, goldens generated in a pinned Linux container. Do not add `alchemist`.** Four of pass 2's five open questions are answered from its decision note, the parked AC table (P1–P7) is gone, and the ACs below are one consolidated set.
>
> **`blocked_by` changed.** #493 and #547 are both closed. **#413 is now a blocker** — it owns `dart_test.yaml` and decides *when* suites fire, which this story consumes rather than decides (see *The division of labour with #413*).
>
> ⚠️ **Both #547's report and its own decision note say `develop` is untouched. That is false for the note itself.** All 324 lines of `documentation/architecture/golden-mechanism-decision.md` are on `develop`, committed by `a7a63865` under the message *"Add image assets for app chip widget test failures"* — which names none of it. The *prototypes* really are only on the unpushed branch `spike/547-golden-mechanism`, so that half holds. **Consequence: AC 9 was already satisfied before this story starts**, and is restated below as a verified precondition rather than a deliverable.
>
> ⚠️ **The same commit also put four golden *failure* PNGs on `develop`** — `app_chip_isolatedDiff/maskedDiff/masterImage/testImage.png` under `test/ui/core/widgets/common/failures/`. Both halves are already fixed: `78eae82a` removed them, and `7cfd2fb9` added `**/failures/` to `.gitignore:174` behind a comment that cites #547's note by name. So "zero PNGs under `test/`" still holds — **but only because someone cleaned up after the spike.** AC 5 rests on that rule rather than re-deriving it.

---

## The decided mechanism

**Dependency: none.** `flutter_test` only. `CLAUDE.md:77` — *"Never add a new package dependency without checking `pubspec.yaml` first and confirming it isn't already covered by an existing dep"* — needs **no exception**.

`alchemist` lost on its own ground rather than on policy. Measured on the same subject, both arms:

| Arm | macOS-generated vs Linux-rendered | stock exact-match |
|---|---|---|
| **A** — stock `LocalFileComparator` | **0.86 %** — `1032 px of 400×300 = 120 000` | fails |
| **B** — `alchemist`'s *CI* golden | **0.06 %** — 62 px | fails |

Its platform-agnostic CI golden — the whole reason the package would exist for us — is a **16× reduction in drift, not an elimination of it**, so Arm B needs the *same* container mitigation Arm A needs. Having to do that anyway is what removes its justification. With `alchemist`'s other two advantages already neutralised before the spike ran (clean resolution was never in doubt; Ahem removes font nondeterminism for *both* arms), nothing was left that it uniquely solved.

**Mechanism: a golden is a container artifact.** Goldens are generated inside a pinned Linux image matching CI, and CI compares them with the **stock exact-match comparator**. A developer never regenerates a golden on the host. This is verified, not inferred: three regenerations in the container produced one hash (`2978357ffb0940ff…`), and the strict comparator passed against the same image.

**No tolerance comparator.** It was measured and works — the SDK's documented subclass at `flutter_test/lib/src/goldens.dart:155-188`, with `0.0086` the smallest threshold passing both directions. **Rejected:** 0.86 % of this surface is ~1032 px, about a whole chip's painted label, wide enough to absorb the regressions the golden exists to catch — and the absolute budget grows with surface area. Two recorded papercuts: the SDK snippet does not compile as written (throws `FlutterError` without importing `package:flutter/foundation.dart`), and `flutter_test_config.dart` is directory-scoped, so it would apply to every test under `test/`.

**Tag: `goldens` via `@Tags`, excluded with `--exclude-tags goldens`.** It is an *exclusion* tag — which slow tests to leave out of the ordinary loop — and composes with #249's `core` / `release-<ver>` / `story-<issue>`, which answer suite, release and story membership. A golden test may legally carry both `goldens` and `story-488`. Nothing in #249's taxonomy is renamed or replaced.

### Layout — `test/goldens/`, mirroring the path under test

The golden test and its PNG live under the home `test/CLAUDE.md` already declares (user decision 2026-10-03):

```
test/goldens/ui/core/widgets/common/chip_golden_test.dart
test/goldens/ui/core/widgets/common/goldens/app_chip.png
```

This is the shape `test/unit/`, `test/widget/` and `test/db_live/` already use — the directory holds the tests and is selectable by path. **It deliberately departs from the spike's prototype layout**, which co-located PNGs at `test/ui/core/widgets/common/goldens/`; that was a path choice, not a measured one, and nothing in the figures depends on it. The note's regeneration line `git add test/**/goldens` becomes `git add test/goldens` accordingly.

**The tag is still required.** Directory placement cannot exclude these: a bare `flutter test` sweeps everything under `test/`. Placement-based exclusion only works *outside* the swept tree, which is why flows live at `integration_test/` — see *Out of scope*.

### The division of labour with #413

#547 deliberately proposed no CI job, no trigger and no workflow edit, deferring placement to **#413's Q-21**. #413 owns `dart_test.yaml` and *when* suites fire; this story builds the invocation and consumes the trigger. That is the same boundary #413 already set with **#554**, which builds the e2e CI job itself because the provisioning is inseparable from making the suite run, while #413 keeps the scheduling.

| Fact | Owner |
|---|---|
| `dart_test.yaml` and the `goldens` tag **key** | **#413** — its AC requires a `tags:` block for `core`, `db_live`, `goldens`, `perf` |
| **When** the golden suite fires | **#413** (Q-21) |
| The `@Tags(['goldens'])` annotation, the CI step that invokes it, the artifact upload, the `--update-goldens` guard | **#488** (this story) |
| The container, the `Dockerfile`, the regeneration path | **#488** |
| Backfilling the 22 Material chips and 4 `AppChip` call sites | **#494** |

⚠️ **Exclusion does not depend on #413 landing first.** `--exclude-tags goldens` already selects nothing without the file — verified: *"No tests match the requested tag selectors: exclude: `goldens`"*. The file's only purpose is silencing a per-run warning (*"A tag was used that wasn't specified in `dart_test.yaml`"*). The dependency exists for the **trigger**, not the exclusion.

⚠️ **Corrected 2026-10-03, hours after this section was first written. #413 has already placed `goldens`.** Its AC-1 suite table assigns `goldens` to **every PR, once #488/#547 land**, on `ubuntu-latest`, excluded from the plain local run by tag — so the trigger is decided and AC 4 consumes it rather than awaiting it. The earlier wording here said #413 *"answered Q-21 for `perf`, not for `goldens`"* and concluded AC 4 must not assume per-PR. Q-21's text really is *"Where does the `perf` suite run?"*, resolved nightly because `perf` seeds ~17,400 rows — but that is one open question, not the whole story, and #413's AC table covers every suite including this one. **The inference was wrong, not the fact.**

### Regeneration

```sh
# One-time, cached thereafter:
docker build --platform linux/amd64 -f tool/goldens/Dockerfile -t myapp-goldens:3.44.4 .

# Each time a golden legitimately changes:
docker run --rm --platform linux/amd64 \
  -v "$PWD":/work -v "$HOME/.pub-cache-linux":/pubcache -w /work \
  myapp-goldens:3.44.4 \
  bash -c 'flutter pub get && flutter test --tags goldens --update-goldens'

git add test/goldens && git commit -m "chore: regenerate goldens"
```

The note carries the `Dockerfile` verbatim (`FROM ubuntu:24.04`, Flutter fetched from the release tarball because `ghcr.io/cirruslabs/flutter:3.44.4` **does not exist**). Two parts of it are load-bearing:

- **`FLUTTER_VERSION` must track `ci.yml`'s pin** — `flutter-version: '3.44.4'` at `ci.yml:41`.
- **The two `git config --global --add safe.directory` entries are not optional.** Without them `flutter` refuses to run against a bind-mounted git tree owned by another uid.

Two operational traps, both found the hard way during the spike, which the note says *"belong in whatever story implements this"*:

- **`PUB_CACHE` must be a host-mounted volume.** With the cache inside the container, `--rm` destroys it while `.dart_tool/package_config.json` survives on the host pointing into the deleted path. The next run fails with a wall of `Error when reading '/pubcache/…': No such file or directory` — it reads like a corrupt checkout; it is a missing volume.
- **The container's `.dart_tool` and the host's conflict.** Run against a copy, or accept that a container `flutter pub get` rewrites the host's `package_config.json`.

---

## Grounding

*Re-verified on `develop` 2026-10-03 (pass 3). Every absence claim was run unpiped with grep's own exit status read — a piped `| head` reports `head`'s status and reads as a clean negative.*

- **Still greenfield.** Zero **occurrences** across a 706-file corpus (`lib/`, `test/`, `pubspec.yaml`, `.github/`) for each of `matchesGoldenFile`, `goldenFileComparator`, `flutter_test_config`, `alchemist` and `golden_toolkit`. No `dart_test.yaml`, no `test/goldens/`, no `tool/`, no `scripts/`. **0** `.png` files under `test/`, and **0** `@Tags` occurrences across 288 `.dart` files under `test/`. None of the spike's prototype files exist on `develop` (`test/flutter_test_config.dart`, `chip_golden_test.dart`, `chip_alchemist_test.dart`).
- **The app theme reaches a test.** `buildAppTheme` is declared at `lib/ui/core/theme/app_theme_builder.dart:17` (`ThemeData buildAppTheme({`), `ThemeData(` occurs **0** times in `lib/main.dart`, and `createTestApp` (`test/test_helpers.dart:142-175`) takes `{required Widget child, List<ChangeNotifierProvider>? providers, bool useAppTheme = false, bool isDark = false, AccentColor accent = AccentColor.amber}`. A chip golden can render the #232 restyle it exists to guard, through the real theme, across light/dark and accent variants. *(#493, shipped 2026-09-13, closed pass 1's one CONTRADICTED row.)*
- **CI is a single job.** `.github/workflows/ci.yml` is **61 lines** and declares **one** job, `test:` (`:29`), `runs-on: ubuntu-latest` (`:31`), Flutter pinned at `:41`, tests run by `run: flutter test --coverage` at **`:55`**. Adding a step or a second job is a small edit. *(Corrected 2026-10-03: pass 2 recorded the file as 60 lines.)*
- **`ci.yml:9`'s baseline figure is a comment, and it is wrong.** It reads *"is 2m39s and 343% CPU locally"*. #547 measured **248 s (4 m 08 s) at 280 % CPU over 3919 tests**, clean — **low by 1.6× on wall time**. Correcting that comment feeds the `/cycle` watchdog arithmetic and is **not this story's to make**.
- **266 test files** match `*_test.dart` under `test/`. *(The note recorded 265 and pass 2 recorded 264; the figure drifts and the budget below is expressed so that it does not matter.)*
- **Four of the five declared test homes exist**; `test/goldens/` is the only absent one. `test/unit/` has 17 test files, `test/widget/` 26, `test/db_live/` 7. `test/CLAUDE.md:51-53` reads *"`test/goldens/` — `pumpWidget` plus pixel comparison, never auto-update, always user-reviewed. **Not created yet** — story #414 adds it."* **#414 is closed**, so that pointer is dead regardless of this story's outcome — AC 8 fixes it.
- **`AppChip` is declared at `lib/ui/core/widgets/common/chip.dart:59`** and already has **14 widget tests**, none visual — `test/ui/core/widgets/common/chip_test.dart` is 298 lines with 12 `testWidgets(` + 2 `test(` across 8 `group(`s.
- **Chip inventory, re-counted 2026-10-03 and unchanged from pass 2:** **23** Material chip constructor occurrences across **10** distinct files — `Chip(` ×4, `FilterChip(` ×11 in 7 files, `ActionChip(` ×8 in 2 files, and **0** each of `InputChip(` and `ChoiceChip(`. One of the 23 is commented out (`main_item.dart:232`, `//ActionChip(`), giving **22 live**, two of which are inside `AppChip` itself (`chip.dart:100`, `:131`). Separately **4 `AppChip` call sites** — `chip_wrap.dart:77` and `routine_detail_view.dart:87`, `:89`, `:203` — the fifth occurrence being the declaration at `chip.dart:73`. All of this is **#494's** scope, not this story's.
- **`.gitignore:174` is `**/failures/`**, behind a comment block at `:168-173` naming `a7a63865`, `78eae82a` and #547's decision note.
- **The decision note is present on `develop`** at `documentation/architecture/golden-mechanism-decision.md`, **324 lines**, byte-identical to the working tree.

---

## Acceptance criteria

**#488 is the single golden-testing story**, absorbing #421 and #414. Pass 1 carried their ACs over verbatim with conflicts marked; pass 2 split them into live and parked; **pass 3 consolidates them into one set.** The parked table is gone — P1, P2, P3 and P6 are decided above, P5 is superseded, P4 is split between AC 11 and AC 12, and P7 is AC 2.

1. (+) `test/goldens/` exists, mirroring the path under test, holding `ui/core/widgets/common/chip_golden_test.dart` and its PNG.
2. (+) **The determinism proof is one `AppChip` golden** — badge and tappable, selected and unselected — rendered through `createTestApp(useAppTheme: true)` so it exercises real `buildAppTheme` output rather than a bare `MaterialApp`. **This subject is fixed, not illustrative:** every figure in this story was measured on it at 400×300, so substituting a subject invalidates the budgets. Real views are #494's.
3. (+) **The golden is generated in the pinned container and passes the stock exact-match `LocalFileComparator` in CI.** Three consecutive container regenerations produce one identical hash. ⚠️ **This replaces pass 2's "the same golden passes on macOS and on `ubuntu-latest`"**, which #547 disproved: host-generated goldens drift 0.86 % on Arm A and 0.06 % on Arm B, and both fail exact-match. The old wording also contradicted AC 10, which requires macOS not to compare them at all.
4. (+) **Goldens execute in CI and fail the build on a diff**, on the job and trigger **#413 defines** — this story writes the invocation, not the schedule. The implementing PR links (a) a red CI run from a throwaway commit that visibly changes the proof golden's widget, and (b) a green run after reverting it.
5. (+) Every CI run of the golden suite, pass or fail, uploads a workflow artifact — the upload step runs even when the test step fails. On failure it holds the master, test and diff images for each failing golden from `failures/`; on a pass, the goldens that were compared. Both demonstration runs in AC 4 link their artifact. ⚠️ **`failures/` is gitignored (`.gitignore:174`) and must stay so** — four such images reached `develop` once already and had to be removed by `78eae82a`.
6. (+) Goldens are never auto-updated. A CI step fails the build if `--update-goldens` appears in any file under `.github/workflows/`, and `test/CLAUDE.md` states that agents must not run it and must instead report the documented regeneration command for a human to run and review.
7. (+) **The regeneration path lives where a developer looks, not only in a dated decision note.** `tool/goldens/Dockerfile` is committed, and the regeneration commands plus **both operational traps** (the host-mounted `PUB_CACHE` volume; the container-vs-host `.dart_tool` conflict) are recorded in `test/CLAUDE.md` or `documentation/`. The `Dockerfile`'s `FLUTTER_VERSION` matches `ci.yml:41`.
8. (+) `test/CLAUDE.md`'s `test/goldens/` entry is made true. The directory exists, and *"**Not created yet** — story #414 adds it"* (live at `:51-53`, and **#414 is closed**) is replaced by a pointer to the regeneration path.
9. (+) **Precondition, already satisfied — verify, do not re-do.** The mechanism decision and its rationale are recorded under `documentation/architecture/golden-mechanism-decision.md`, 324 lines, on `develop`. Confirm it is still present and unmodified; do not re-argue the decision inside this story.
10. (−) Goldens do not run in the plain local `flutter test` invocation. Proven by a test-count comparison: the suite reports the same total with and without `--exclude-tags goldens`. **Directory placement is not sufficient** — a bare `flutter test` sweeps all of `test/`.
11. (+) **The local budget is a stated zero, not a number to discover.** The golden cases are excluded from the ordinary loop, so the in-loop delta is zero by construction; `--exclude-tags goldens` must leave the pre-existing test count exactly unchanged. One golden runs in ~4.5 s standalone. The reference baseline is #547's measured **248 s / 3919 tests / 280 % CPU**, which supersedes `ci.yml:9`.
12. (+) **The implementing PR runs one `workflow_dispatch` of `ci.yml` and records two figures the spike could not get** (user decision 2026-10-03): the **CI wall-time delta**, and **whether a container-generated golden passes exact-match on `ubuntu-latest` natively**. #547's container was `linux/amd64` **emulated on Apple Silicon**, so its 15–18 s per golden measured the emulator; and "CI needs no Docker" is an **inference it never ran**. Neither could be obtained before a branch carried a golden test, which is why this is an AC here rather than a blocker. **If the native comparison comes back false**, Arm A still stands — CI then runs the container or adopts a tolerance — and that outcome is recorded rather than worked around.
13. (−) **No golden is committed from an unpinned or ad-hoc platform.** Every committed PNG is container-generated by the documented path; regenerating on the host is not a sanctioned route. CI enforces this by construction — a host-generated golden drifts 0.86 % and fails the stock exact-match comparator — and **#494 depends on this rule being stated here**, since its own AC forbids committing a golden from any environment other than the one this story prescribes.
14. (−) No new package dependency. `pubspec.yaml` and `pubspec.lock` gain nothing; `CLAUDE.md:77` needs no exception.
15. (−) This story does not create `dart_test.yaml` (#413 owns it) and does not decide **when** the suite fires (#413's Q-21).
16. (−) No e2e, no device, no entitlement axis — goldens are headless and mocked.
17. (−) Not a blanket golden pass over every view; one subject proves the layer.
18. (−) No production code changes: this story adds tests and test infrastructure only.
19. (−) `dart format .` clean, `flutter analyze` clean, `flutter test` green.

### Anti-faking guidance

- **A golden that renders a bare `MaterialApp` proves nothing.** The whole point is the #232 `chipTheme`, so the proof golden must go through `createTestApp(useAppTheme: true)`. A golden built without it would pass identically before and after the restyle it exists to guard.
- **Do not satisfy AC 3 by generating on the host and asserting it passes locally.** That is the configuration #547 measured at 0.86 % drift. The claim is about container-generated bytes compared by the stock comparator, and the evidence is three regenerations yielding one hash.
- **AC 10's evidence is a test count, not an assertion that a tag exists.** A `@Tags` annotation that is present but mis-spelled still greps as present; only the count proves the exclusion selected what it should. #547's own proof was that both runs reported the same 3919 tests.
- **A skipped or absent run is not a passing run.** AC 4 and AC 12 are satisfied by linked CI runs, not by local output. There is no stack to be unavailable here, but there is a workflow that may simply not have been dispatched.
- **AC 12 must report a negative honestly.** It exists because the spike refused to write an emulated figure as a CI delta. Recording "the native comparison failed, so CI runs the container" satisfies it; quietly adopting a tolerance to make the golden pass does not.

## Open questions

<!-- Auto-maintained by /refine. Edit answers here only if you want them treated as resolved. -->

**Pass 3 (2026-10-03) — all questions resolved.** #547's decision note answered four; the user answered five.

- [x] ~~(Deps) `alchemist` (#249 D-5) or no new package (#421 / standing rule)?~~ → **No new package. `flutter_test` only.** `alchemist`'s CI golden still drifts 0.06 % / 62 px across hosts, still fails exact-match, and so needs the same container mitigation Arm A needs — a dependency bought a 16× smaller number that is still non-zero. `CLAUDE.md:77` needs no exception. (resolved 2026-10-03)
- [x] ~~(Mechanism) Which platform mechanism?~~ → **Goldens are generated in a pinned Linux container; CI compares with the stock exact-match comparator.** The rule is *a golden is a container artifact*, never regenerated on the host. The tolerance comparator was measured and rejected — `0.0086` is ~1032 px on this surface. (resolved 2026-10-03)
- [x] ~~(AC) Keep or drop the "dev- and CI-generated goldens are byte-identical" AC?~~ → **Keep, re-scoped to *generated in the CI container*.** True there (3/3 one hash); false for host-generated goldens on both arms, so as written it asserted something no mechanism delivers. Now AC 3. (resolved 2026-10-03)
- [x] ~~(Scope) Does `dart_test.yaml` belong to this story? (was P6)~~ → **No — #413 owns it**, and its AC already requires a `tags:` block declaring `core`, `db_live`, `goldens`, `perf`. Exclusion works without the file; its absence costs only a warning. Now AC 15. (resolved 2026-10-03)
- [x] ~~(Deps) Who builds the CI invocation that runs the golden suite?~~ → **This story builds it; `blocked_by` #413 for the trigger.** Mirrors the boundary #413 already set with #554, which builds its own job while #413 keeps the scheduling. (resolved 2026-10-03)
- [x] ~~(Risk) The CI wall-time budget, and the unproven "CI needs no Docker" inference.~~ → **An AC on the implementing PR**, not a blocker — neither figure can be obtained before a branch carries a golden test. Now AC 12. (resolved 2026-10-03)
- [x] ~~(Scope) What subject proves the layer? (was P7)~~ → **`AppChip` only**, exactly #547's measured subject, because every budget and determinism figure describes it. Real views stay with #494. Now AC 2. (resolved 2026-10-03)
- [x] ~~(AC) Where does the regeneration path live?~~ → **Lifted into a durable home**; AC 9 becomes a verified precondition since the note is already on `develop`. Now ACs 7 and 9. (resolved 2026-10-03)
- [x] ~~(Scope) Where do the golden files and the golden test live?~~ → **`test/goldens/`, mirroring the path under test**, matching the home `test/CLAUDE.md` declares and the shape `test/unit/` / `test/widget/` / `test/db_live/` use. Departs from the spike's co-located prototype, which was a path choice and not a measured one. (resolved 2026-10-03)
- [x] ~~(Scope) What does #488 become: the single golden-foundation story, or a decision record?~~ → #488 absorbs both #421 and #414, which close `superseded:merged`; #488 moves under #249. (resolved 2026-09-13)
- [x] ~~(Deps) Is `alchemist` 0.14.0 compatible with Flutter 3.44.4?~~ → **Yes, and it resolves.** `sdk >=3.8.0 <4.0.0`, `flutter >=3.32.0`; `pub add --dry-run` exits 0. Moot now that the dependency is declined on other grounds. (resolved 2026-09-27)
- [x] ~~(Structural) Does the app theme actually reach a test now?~~ → **Yes — #493 shipped.** `buildAppTheme` is importable, `createTestApp(useAppTheme:, isDark:, accent:)` renders through it, `ThemeData(` is gone from `main.dart`. (resolved 2026-09-27)
- [x] ~~(Data) Fonts: accept the test fallback, or bundle a real font?~~ → **Accept the fallback, deliberately.** It is **Ahem** (`flutter_test/lib/src/binding.dart:2664`; `flutter_tools/static/Ahem.ttf`) — deterministic block glyphs on every platform, so no font is bundled and no `flutter_test_config.dart` font loading is added. **Stated trade-off:** these goldens verify layout, spacing, colour and shape, **not glyph rendering**; a typeface regression is out of their reach. (resolved 2026-09-27)
- [x] ~~(Structural) Extracting app `ThemeData` into an importable builder: in scope, or a prerequisite?~~ → Prerequisite story #493. (resolved 2026-09-13)
- [x] ~~(Scope) Chip call-site backfill: in the foundation story or a follow-up?~~ → Follow-up story #494, `blocked_by` #488. (resolved 2026-09-13)
- [x] ~~(AC) "CI goes red on a deliberate visual change": durable AC or one-off demonstration?~~ → A demonstration recorded in the PR — a red run from a throwaway commit, then a green run after the revert. Now AC 4. (resolved 2026-09-13)
- [x] ~~(Risk) What makes the "does not slow `flutter test`" negative AC testable?~~ → Both an exclusion guarantee and a figure. Now ACs 10 and 11, and the figure turned out to be **zero by construction**. (resolved 2026-09-13)
- [x] ~~(Behavior) On a golden failure in CI, are the diff images uploaded?~~ → Upload always, pass or fail. `failures/` is only written on failure, so a passing run's artifact holds the goldens that were compared. Now AC 5. (resolved 2026-09-13)
- [x] ~~(Behavior) How is "never auto-updated" enforced?~~ → CI check plus agent rule. Now AC 6. (resolved 2026-09-13)
- [x] ~~(Deps) Does this need `blocked_by` #412?~~ → No. #412 shipped via PR #491. (resolved 2026-09-13)

## Open spikes

**None.** SPIKE-1 became **#547**, which ran on 2026-10-02 and closed `completed` — 1-hour box, **1 h 25 m actual, reported not hidden**, all of the overrun being Arm A's container (the `ghcr.io/cirruslabs/flutter:3.44.4` image does not exist, so one had to be built; it then failed on arm64 and was rebuilt `--platform linux/amd64`). Its decision note is on `develop` and this story consumes it.

## Out of scope

- **The chip call-site backfill** — **#494**, `blocked_by` this story: 22 live Material chips across 10 files plus 4 `AppChip` call sites.
- **`dart_test.yaml`, and when the golden suite fires** — **#413**, which this story is `blocked_by`.
- **Correcting `ci.yml:9`'s wrong baseline comment** (*"2m39s and 343% CPU"*, low by 1.6×). It feeds the `/cycle` watchdog arithmetic and belongs with whoever owns that, not here.
- **`test/CLAUDE.md:60`'s second dead pointer**, recorded so it is not rediscovered: it reads *"`e2e/` — the real app on a real device … **Not created yet** — story #415 adds it."* **#415 is closed**, and #547 proved the path is wrong too — `flutter test` decides a file is an integration test *solely* by whether its path starts with `<project>/integration_test`, so flows live at `integration_test/flows/`. Neither `e2e/` nor `integration_test/` exists at the repo root today. **#554** owns that line; AC 8 fixes only the `test/goldens/` entry.
- **Glyph rendering.** Ahem makes these goldens deterministic and blind to typeface changes at the same time. Stated, not overlooked.

## Related
- #421, #414 — absorbed here, closed `superseded:merged` 2026-09-13
- **#547** — the golden-mechanism spike. Ran 2026-10-02, closed `completed`; its decision note is this story's input
- **#413** — `blocked_by`. Owns `dart_test.yaml` and the trigger (Q-21)
- #493 — prerequisite making the app theme importable from tests. **Shipped**
- #494 — chip call-site backfill. `blocked_by` this story
- #232 (chip restyle, shipped as PR #424), #249 (parent epic 0.36, closed), #543 (`perf`, the other exclusion tag), #554 (e2e infrastructure, same boundary with #413)
- #412 — test-suite rename. Shipped, `test/CLAUDE.md` fixes `test/goldens/` as the home

---

> **Tag-form correction — 2026-09-30, retained.** `story:<issue>` and `release:<ver>` are **not legal tag names**. `package:test` rejects them — *"Invalid tag name. Tags must be (optionally hyphenated) Dart identifiers"* — and `dart_test.yaml` rejects such keys too (*"Invalid tags key: Expected end of input"*, exit 65), quoted or not. Dots fail for the same reason. The legal forms are **`story-<issue>`** and **`release-<ver>`** with dots as hyphens. #249's taxonomy (`:272-274`) is unimplementable as literally written; it is closed, so it stays archival. **#413 owns `dart_test.yaml`** and records the verified mechanism. The `goldens` tag used by this story is a plain Dart identifier and is unaffected.

