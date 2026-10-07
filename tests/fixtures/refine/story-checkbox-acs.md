Split from #249. Carries **Q-3 / Q-11 / Q-12 / Q-17 / Q-18**, plus **Q-21** (added out of #543's refinement). Part decision, part implementation.

> **Q-3 is not missing — it is fused with Q-11.** #249 records them as one entry (`:317-318`): *"**Q-3 / Q-11** — CI or local, per suite? Deferred by decision until D-1's file moves have landed."* Q-11 is the concrete half; answering it answers Q-3.

> **Q-19 was renumbered to Q-21 on 2026-09-30.** #249 already defines **Q-19** as *"which flows ship in D-6's first slice"* (`:337`) and assigns it to **#416** (`:15`), which cites it twice. The `perf`-trigger question added here on 2026-09-29 collided with it; #249's high-water mark is Q-20 (itself filed out as #419), so this is **Q-21**. The citing stories (#543, #488, #547) were updated in the same pass. The 2026-09-29 note comment below still says "Q-19" — log comments are append-only, so the correction lives here rather than being edited into it.

## The problem this exists to fix

`ci.yml`'s test step (`:55`, `run: flutter test --coverage`) sweeps everything under `test/`. That includes `test/db_live/`, whose **7 files self-skip** when no Supabase stack is reachable (`supabase_test_harness.dart:69`, `skipIfUnavailable()`), so they report green on every PR without asserting anything.

**`db_live` is not homeless.** `supabase-ci.yml` genuinely runs it — it boots the local stack (`supabase start` `:41`, `supabase db reset` `:44`), lints (`:47`), runs pgTAP (`:50`), then runs `flutter test test/db_live` with the booted stack's URL and keys injected via `--dart-define` (`:62-72`), on a paths-filtered `pull_request` plus `push` to `develop`/`main`. So the suite has a real home and a real signal.

The actual defect is narrower than "a suite that never runs": **the same 7 files are swept twice** — asserted for real in `supabase-ci.yml`, and silently skipped in `ci.yml`. The silent pass is what makes a green `ci.yml` overstate what was verified, and it is the pattern that must not be repeated for `e2e`, `goldens` or `perf`.

## Grounding (2026-09-30)

- **`ci.yml:41` is `flutter-version: '3.44.4'`**, not the test invocation. The bare `flutter test --coverage` is at **`:55`**. This citation was inherited from #249 `:104` and is wrong in both places; #249 is closed, so it is corrected here only.
- **`test/integration_live/` no longer exists.** It became `test/db_live/` in commit `2dd0acc0` under **#412**, which is closed and is this story's only `blocked_by` — so the rename has already landed and the present tense is `test/db_live/`. All 7 `*_test.dart` files there route through the harness.
- **CI tag selection is greenfield, verified unpiped:** no `dart_test.yaml`, and `.github/workflows/` contains zero references to `e2e`, `goldens`, `perf`, `dart_test` or `integration_test` (grep exit 1 each). The single `tags` hit is a commented-out git-tag trigger (`verify-build-multiplatform.yml:6`). No workflow selects tests by tag today.
- **`schedule:` is a proven trigger here** — `prune-merged-branches.yml` runs `cron: '0 4 1 * *'`. But `verify-build-multiplatform.yml:11-15` records a schedule **removed 2026-08-28** because *"all 5 of its runs over the preceding 60 days failed, so it was burning a weekly run and reporting nothing usable"* — and its comment had claimed daily while the cron fired Mondays. **Evidence against "nightly" for Q-18:** an unattended trigger here has already rotted once, undetected, for 60 days.
- **The last genuine green `ci.yml` run was 2026-09-14.** The 2026-09-20 runs of both `ci.yml` and `supabase-ci.yml` failed at step 2, `actions/checkout@v3`, with every later step skipped — infrastructure, not tests. Noted because this story's wall-clock AC needs a green baseline to measure against; it is **not** this story's bug to fix.

### Re-verified 2026-10-03 (pass 3)

- **The empty-selector exit codes are now measured, not asserted.** On a single real test file:
  `flutter test <file> --tags doesnotexist` exits **79** — *"No tests match the requested tag
  selectors: include: \"doesnotexist\", exclude: \"<none>\""* — while
  `flutter test <file> --exclude-tags doesnotexist` exits **0** and runs the file normally. **The two
  sides are not symmetric**, and the whole goldens ordering question below turns on that asymmetry:
  an exclusion is safe before anything carries the tag, an inclusion is not.
- **`ci.yml` is green again.** Run 2026-10-03 **19:55→20:05 (~10 min)** on `562/strong-export-dataset`
  succeeded, which sits inside the 10.9–13.0 min band recorded above. The 2026-09-20 failure was the
  most recent run until then, so *"red since 2026-09-20"* read correctly when written. **`actions/checkout@v3`
  is unchanged at `ci.yml:33`** — the pin was not bumped, and this pass does not establish what the
  2026-09-20 failure's cause was. What changed is only that **AC 11 now has a green run to measure against.**
- **The Strong dataset is committed.** `test/support/fixtures/strong_workouts.csv` is **1,940,446 bytes**,
  beside 12 CSV micro-fixtures and `test/support/strong_export_fixture_test.dart`. Pass 2's grounding
  recorded that *nothing* matching `*strong*` existed in the working tree; **14 files now match.** See the
  AC 15 correction below.
- **No tag selector exists in CI today**, re-confirmed over all **9** workflow files: **0** occurrences each
  of `e2e`, `goldens`, `perf`, `dart_test`, `integration_test`, `--exclude-tags`, `--tags` and `-x `. Still
  **0** `@Tags` across 288 `.dart` files under `test/`, still no `dart_test.yaml` anywhere in the repo, and
  `test/db_live/` still holds exactly **7** `*_test.dart` files.
- **`supabase-ci.yml` selects `db_live` by path, not by tag** — `flutter test test/db_live \` at `:69`,
  with `supabase test db` at `:50`. So adding `@Tags(['db_live'])` to those 7 files cannot change what that
  workflow runs; AC 4 is a pure non-regression check.
- **Nothing documents the tag vocabulary.** **0** occurrences of `dart_test` or test-tag guidance across the
  root `CLAUDE.md` (78 lines) and `test/CLAUDE.md` (70 lines). This story creates the mechanism and, until
  pass 3, no AC said where anyone would learn it. See AC 18.

## `dart_test.yaml` — this story owns it

**Decided 2026-09-30 (user).** Four stories need one selection file and none owned it:

| Story | What it needs from the file |
|---|---|
| **#554** (e2e substrate) | tag axes declared, so `flutter test -t core` selects the core suite (#249 D-8). *(Was #415 when this table was written — closed `superseded:split`; the `-t core` selection AC now lives with **#550**, which creates the tagged file.)* |
| **#488 / #547** (goldens) | tag-based exclusion of goldens from the plain local run — a hard requirement of whichever arm #547 recommends; #488 parks it as **P6** |
| **#543** (perf) | a `perf` tag to exclude the budget suite locally, added to the one mechanism rather than a parallel scheme |

**This story creates the file and wires the triggers.** The consuming stories declare tags against it rather than inventing selection themselves. **One mechanism, not two.**

### Verified mechanism — measured 2026-09-30, not assumed

Every line below was established by running `flutter test` in a throwaway project on Flutter 3.44.4. They constrain the design, and two of them rule options out:

1. **`flutter test` *does* read `dart_test.yaml`.** A bare `flutter test` with a top-level `exclude_tags` honoured it with no flag passed. Mechanism: `flutter_tools`' `test_wrapper.dart:7` imports `package:test_core/src/executable.dart` and calls `test.main(args)`, and that executable loads the config (`executable.dart:104-110`). `flutter_tools` pins `test: 1.31.0` / `test_core: 0.6.17`.
2. **Presets are unreachable.** `flutter test -P <preset>` fails with *"Could not find an option or flag `-P`"* (exit 64). `flutter test --help` lists no `-P`, no `--configuration`. **So a preset cannot scope an exclusion.**
3. **A top-level `exclude_tags` is global and inescapable.** It applies even when a path is named explicitly — `flutter test test/foo_test.dart` still ran nothing (exit 79) — and **`--tags` cannot override it**, because exclusions take precedence (`include: "x" exclude: "x"` → nothing ran). **So a top-level `exclude_tags: db_live` would break `supabase-ci.yml`'s `flutter test test/db_live`.**
4. **Therefore: the file carries a `tags:` declaration block only, and every exclusion is per-invocation `-x`.** This is forced by 2 and 3 together, not a preference.
5. **Nothing-matched exits 79, not 0.** An over-broad exclusion **fails loudly** rather than passing green. This is what makes AC 2 enforceable rather than aspirational.
6. **Colons are illegal in tag names.** `@Tags(['story:488'])` is rejected — *"Invalid tag name. Tags must be (optionally hyphenated) Dart identifiers"* (exit 1) — and `dart_test.yaml` rejects such keys too (*"Invalid tags key: Expected end of input"*, exit 65), quoted or not. **#249's `release:<ver>` / `story:<issue>` taxonomy is unimplementable as literally written.** Dots fail for the same reason, so a version's dots become hyphens.
7. **An undeclared tag is a warning, not an error.** `flutter test` lists every undeclared tag and still exits 0. This is what makes the declaration policy below viable.

### The vocabulary, in legal form

| Tag | Axis | Declared in `dart_test.yaml`? |
|---|---|---|
| `core` | membership — the always-firing suite | **yes** |
| `db_live` | exclusion — needs a live Supabase stack | **yes** |
| `goldens` | exclusion — slow / platform-sensitive | **yes** |
| `perf` | exclusion — seeds ~17,400 rows | **yes** |
| `story-<issue>` (e.g. `story-488`) | membership — traceability | **no** — warning accepted |
| `release-<ver>` (e.g. `release-1-2-0`) | membership — release gating | **no** — warning accepted |

**Declaration policy (user decision 2026-09-30): declare only the stable suite tags.** Per-story and per-release tags are not declared, because declaring them would mean a config edit per story and per release forever. The cost is a warning line listing them on every run; the benefit is that #417's traceability scheme needs no config churn. The warning must **not** be escalated to an error.

`flow` is **not** a tag at all — it is directory structure (`integration_test/flows/<flow>_test.dart`), per #249 D-8.

## Open questions

<!-- Auto-maintained by /refine. Edit answers here only if you want them treated as resolved. -->

**Pass 3 (2026-10-03) — re-opened and closed.** Three premises had moved since the 2026-10-02
sign-off and one gap surfaced from grounding. All four are resolved.

- [x] ~~(Risk) The `goldens` inclusion hazard — `--tags` on an empty selector exits 79.~~ →
  **This story lands the exclusion only.** The `goldens` key and `-x goldens` are safe here (exclusion
  exits **0** with nothing tagged); the `--tags goldens` step belongs to **#488**, which supplies the
  first golden test. Measured, not assumed: the two sides are not symmetric. Now **AC 17**, and the
  AC-1 table row says *"inclusion wired by #488, not here"*. (resolved 2026-10-03)
- [x] ~~(Data) AC 15's premise has dissolved — #544 is closed `NOT_PLANNED`.~~ → **Restated
  generically, with every #544 reference dropped**: the `perf` nightly fails rather than skips when it
  cannot seed to the required scale, whatever the source. Kept because *never skip green* is this
  story's point; untied from any issue number, which is what let it go stale in four days.
  (resolved 2026-10-03)
- [x] ~~(AC) AC 11's baseline is obtainable now, but its e2e half cannot be measured here.~~ →
  **AC 11 covers this story's own change only**, against the 2026-10-03 green run. The `e2e core`
  delta moves to **#554**, the only story that can measure it — requiring it here would be a
  dependency cycle, since #554 is `blocked_by` this story. ⚠️ **#554 carries no AC for it today**;
  flagged in AC 11 and by comment on #554. (resolved 2026-10-03)
- [x] ~~(Scope) Nothing documents the tag vocabulary.~~ → **Now AC 18** — `test/CLAUDE.md`, beside
  the five suite homes it already records: which tag each suite carries, hyphenated Dart identifiers
  only, and that an undeclared tag warns rather than fails. (resolved 2026-10-03)

- [x] ~~(Risk) **Q-3 / Q-11** — `test/db_live/` in CI: boot the stack, make the skip loud, or exclude it?~~ → **Exclude it from `ci.yml` by tag** (user decision 2026-09-30). The 7 files gain a library-level `@Tags(['db_live'])`, and `ci.yml`'s invocation passes `-x db_live`. `supabase-ci.yml` is **unaffected** precisely because the exclusion is per-invocation rather than a top-level `exclude_tags` — see *Verified mechanism* 3. All 7 files open with `//` comments and have no `library` directive, so the annotation drops in above the imports cleanly. (resolved 2026-09-30)
- [x] ~~(Risk) **Q-12** — PR CI runtime budget?~~ → **A delta, not an absolute ceiling: `core` adds ≤ 6 minutes** over the measured baseline (user decision 2026-09-30). Expressed as a delta so it survives baseline drift as the unit/widget suites grow, and consistent with how #488 and #543 state their budgets. The 6 minutes must absorb an Android emulator boot (commonly 2–4 min), so the flow itself has roughly 2–4 min of room — if it needs more, that is a finding to report, not a reason to quietly raise the number. **Measured 2026-09-30, replacing #249's unverified "~8.5 min":** successful `ci.yml` PR runs took **10m52s, 12m30s, 13m00s, 12m50s**, plus `workflow_dispatch` runs at 12m55s and 10m56s — **median ≈ 12m50s, range 10.9–13.0 min (n=6, all 2026-09-14)**. These are run-level `created_at` → `updated_at` spans and therefore include queue time, so they are an upper bound on compute. What headroom is acceptable once #249 D-9 puts the `core` e2e suite on every PR?
- [x] ~~(Risk) **Q-17** — Which mobile platform?~~ → **Android on `ubuntu-latest`** (user decision 2026-09-30). It keeps `core` on the existing runner class so it can actually gate every PR per #249 D-9, and fits the ≤ 6 min delta. **Recorded trade-off: iOS-specific regressions are out of e2e's reach entirely** — the same shape as #488's accepted Ahem trade-off, where goldens verify layout but never glyphs. Accepted deliberately, not overlooked. See AC 16. **Not a free choice:** dev machines are macOS (iOS simulator available), `ci.yml` and `supabase-ci.yml` both run `ubuntu-latest` (Android emulator viable, iOS impossible). Choosing iOS implies macOS runners or local-only execution. Follows from Q-18.
- [x] ~~(Risk) **Q-18** — What triggers the non-`core` flows?~~ → **A nightly schedule** (user decision 2026-09-30), chosen over post-merge. ⚠️ **This is the pattern that already rotted here**, so AC 12's detection mechanism is load-bearing rather than a nicety: `verify-build-multiplatform.yml`'s cron failed 5/5 runs across 60 days unnoticed, *and* its comment claimed daily while the cron fired Mondays. Two distinct rot modes — failing runs, and a cadence that does not match its own description. Original framing: #249 D-9 puts only `core` on PRs; the rest need a home or they never run. **Weigh the removed-cron evidence above**: whichever trigger is chosen needs a way to notice it has stopped reporting.
- [x] ~~(Scope) **Q-21** — Where does the `perf` suite run?~~ → **Nightly, alongside the flows, wired now behind a loud guard** (user decision 2026-09-30). **#544 has not committed the dataset**: verified 2026-09-30 that nothing matching `*strong*` exists in the working tree — the 1.94 MB export sits only at `~/Downloads/strong_workouts.csv`, and #544 is `Draft` with no `Depth` and three unresolved questions including an unfinished privacy review of 24 note strings bound for permanent git history. So `perf` is wired immediately and **fails loudly when the dataset is absent** rather than skipping green. **No `blocked_by` edge is added**, keeping this story independent; the guard is AC 15. (#543's "#544 is not a blocker" holds for #543 shipping its budgets, but a nightly job seeding nothing would be exactly the silent-absence failure this story exists to prevent.) Original framing: *(Added 2026-09-29 out of #543's refinement; renumbered from Q-19 on 2026-09-30.)* **#543** introduces a performance-budget suite and deliberately declares a `perf` tag **without wiring CI**, deferring the trigger here. It is excluded from the plain local run by design, because it seeds ~17,400 rows through the real schema. Its budgets **fail the build** when exceeded, so the trigger choice decides whether they gate anything. Same shape as Q-18 and needs the same answer: a trigger, a runner, and defined behaviour when preconditions are absent. ⚠️ **The #544 facts in this resolution went stale within four days — see the AC 15 correction.** #544 is closed `NOT_PLANNED` and split into #562 (dataset, shipped) and #563 (loader, open); the privacy review it flagged landed with #562. The *decision* — nightly, behind a loud guard — stands; only its stated grounds moved.

## Acceptance Criteria

- [ ] (+) Each suite has the home decided in this pass, implemented and documented:

  | Suite | Trigger | Runner | If preconditions absent |
  |---|---|---|---|
  | `unit`, `widget` | every PR (`ci.yml`) | `ubuntu-latest` | n/a |
  | `db_live` | paths-filtered PR + push to `develop`/`main` (`supabase-ci.yml`) | `ubuntu-latest` | stack booted by the job; excluded from `ci.yml` via `-x db_live` |
  | `goldens` | every PR — **inclusion wired by #488, not here** | `ubuntu-latest` | excluded from the plain local run by tag (`-x goldens`, exit **0** with nothing tagged) |
  | `e2e` — `core` only | every PR (#249 D-9) | `ubuntu-latest`, Android emulator | fail, never skip |
  | `e2e` — non-`core` flows | **nightly** | `ubuntu-latest`, Android emulator | fail, never skip |
  | `perf` | **nightly** | `ubuntu-latest` | **fail loudly when it cannot seed to scale** — never skip green; see AC 15 |

- [ ] (+) No suite can pass by being silently skipped: a skipped suite either fails the run, or is explicitly excluded from that trigger by configuration — never by accident.
- [ ] (+) **`test/db_live/` no longer registers a silent pass in `ci.yml`.** Its 7 files carry `@Tags(['db_live'])` and `ci.yml`'s test step passes `-x db_live`.
- [ ] (+) **`supabase-ci.yml` still runs all 7 `db_live` files**, proven by an observed test count rather than assumed — the regression this guards against is converting a silent pass into a silent absence.
- [ ] (+) **`dart_test.yaml` exists**, created by this story, containing a `tags:` declaration block for `core`, `db_live`, `goldens`, `perf` — and **no top-level `exclude_tags` or `include_tags`**, because a top-level exclusion cannot be overridden by path or by `--tags`.
- [ ] (+) Every exclusion is expressed **per invocation** via `-x`, in the workflow or command that needs it. No preset is used; `flutter test` rejects `-P`.
- [ ] (+) All tag names are legal: hyphenated Dart identifiers, never colon-bearing. `story-<issue>`, `release-<ver>` with dots as hyphens.
- [ ] (+) Tag selection demonstrably works: `flutter test -t core` selects only the core suite, and the plain local `flutter test` excludes `goldens`, `perf` and `db_live`. Shown by a test-count or named-test comparison, not asserted in prose.
- [ ] (+) `ci.yml` implements the decision.
- [ ] (+) Q-17's platform choice is recorded with the runner constraint that drove it.
- [ ] (+) **Measured PR wall-clock before and after — for the change this story makes**, taken from a **green** run. That means the delta from the `db_live` exclusion and tag selection, against the 2026-10-03 green baseline (~10 min), superseding #249's "~8.5 min". **The `e2e core` delta against Q-12's ≤ 6 min budget is deliberately *not* measured here** (user decision 2026-10-03): it needs the Android emulator job, which is **#554's** provisioning, and #554 is `blocked_by` this story — so requiring it here would be a dependency cycle. ✅ **#554 now carries that AC** (added in its pass 2, hours after this line was written): it measures the `e2e core` delta from a green run and **reports a breach rather than raising the number**, which is this story's own rule for the budget. *(This sentence previously read "That measurement has no AC in #554 today — #554 has 14 ACs and references the ≤ 6 min budget only in its Related section". True when written; #554 now has 17.)*
- [ ] (+) **A PR-time freshness assertion notices a dead nightly** (user decision 2026-09-30). `ci.yml` — which runs on every PR and is actually watched — fails if the most recent **successful** nightly run is older than an agreed threshold, and its failure message says which suite is stale and why the PR is blocked. Chosen because it catches **both** observed rot modes: runs that fail, and a schedule that stops firing or fires on a cadence other than the one it claims. An `if: failure()` notifier alone would miss the second, since a schedule that never fires produces no failure. Note there is no `if: failure()` pattern in any of the 9 workflows today, while `gh issue create` automation already exists (`review-comment-to-issue.yml:124`) if a notifier is added later.
- [ ] (−) **Writes no test logic.** It adds a library-level `@Tags` annotation to 7 existing `db_live` files and creates `dart_test.yaml` — an annotation and a config file, not authored test behaviour. *(This clause was "does not write any test" before 2026-09-30; narrowed when the tag-exclusion mechanism was chosen, so the boundary stays honest rather than being quietly breached.)*
- [ ] (−) Does not create `integration_test/flows/` or any flow file; that is **#554** (the e2e
  infrastructure half of #549, which was split on 2026-10-01).
- [ ] (+) **AC 15 — the `perf` nightly fails rather than skips when it cannot seed to the required scale**, whatever the source of the data. It must exit non-zero with a message naming what was missing — never pass, never skip green. **Self-enforcing, and now measured rather than asserted:** `flutter test --tags perf` exits **79** with *"No tests match the requested tag selectors"* when nothing carries the tag, so an empty `perf` run already fails.
  > ⚠️ **Restated 2026-10-03; the previous wording's premise had dissolved.** It read *"With #544 unshipped, the job must exit non-zero with a message naming the absent fixture"* and keyed the guard's removal to *"once #544 commits the data"*. **#544 is closed `NOT_PLANNED`**, split 2026-10-03 into **#562** (commit the dataset — closed `COMPLETED`; the 1.94 MB export and 12 micro-fixtures are on `develop`) and **#563** (the loader — open). So the story named three times here will never commit anything, and the data it was waiting for already arrived from elsewhere. Separately, **#543 states it is "deliberately not `blocked_by` #544"** and seeds synthetically at the same characterisation scale — so the absent fixture may never have gated it at all. The guard is kept because *never skip green* is this story's whole point, but it is no longer tied to any issue number, which is what let it go stale in four days.
- [ ] (+) **AC 16 — the iOS gap is stated, not implied.** Documentation of the e2e suite records that it runs Android only and that iOS-specific regressions are outside its reach, so nobody reads "e2e green" as cross-platform assurance.
- [ ] (−) Does not touch the `actions/checkout@v3` pin (`ci.yml:33`, unchanged); it only needs a green run to measure against, and **one now exists** (2026-10-03, ~10 min). *(Pass 2 worded this as "the failure that has been red since 2026-09-20" — accurate then, since that was the latest run; superseded 2026-10-03.)*
- [ ] (−) **AC 17 — no `--tags goldens` invocation is added by this story** (user decision 2026-10-03). The `goldens` key in `dart_test.yaml` and `-x goldens` on the plain run both land here and are safe with nothing tagged — exclusion exits **0**. The *inclusion* step belongs to **#488**, which supplies the first golden test and is `blocked_by` this story: a `--tags goldens` step added before it would exit **79** and **fail every PR**. Same division as #554, which builds its own job while this story decides when it fires.
- [ ] (+) **AC 18 — the tag vocabulary is documented where a developer or agent will find it** (user decision 2026-10-03): `test/CLAUDE.md`, beside the five suite homes it already records. It states which tag each suite carries, that tag names must be **hyphenated Dart identifiers** and never colon-bearing, and that an undeclared tag warns rather than fails. Grounded gap: **0** occurrences of `dart_test` or tag guidance across the root `CLAUDE.md` and `test/CLAUDE.md` before this story.

## Related

- **#249** (closed parent epic) — source of Q-3/Q-11/Q-12/Q-17/Q-18, D-8's tag taxonomy (`:272-274`) and D-9 (`core` on every PR, `:279-286`). Three of its claims are stale and corrected here: the `ci.yml:41` citation, the `test/integration_live/` path, and **the colon-bearing tag forms, which `package:test` rejects outright**. Closed, so left archival.
- **#412** — the rename, closed; `test/integration_live/` → `test/db_live/` (`2dd0acc0`). This story's only `blocked_by`, already satisfied.
- **#554** — `blocking`: consumes this file. It is the live successor to #415 → #549 (both closed
  `superseded:split`). ✅ **The tag-axis over-claim is resolved.** #415's AC said `dart_test.yaml`
  "defines the `core`, `release-<ver>` and `story-<issue>` tag axes", which over-claimed the
  declaration policy above; the narrowing that line asked for happened in the splits. #554 carries
  **no** `-t core` AC at all (verified 2026-10-01: zero occurrences), and the selection claim now
  lives with the story that creates the tagged file — **#550**, whose AC reads *"carrying the `core`
  tag so `flutter test -t core` selects it"*.
- **#551 / #552 / #417** — carry and read `story-<issue>` tags; all rely on undeclared tags warning
  rather than failing (*Verified mechanism* 7). #551 and #552 each carry the AC explicitly (verified
  2026-10-01); they are the live successors to #416, closed `superseded:split` on 2026-09-30.
- **#488 / #547** — goldens; **P6** parks `dart_test.yaml` on #547's AC 7, which this story now answers by owning the file.
- **#543** — perf; declares the `perf` tag, defers its trigger to Q-21. No dependency edge in either direction, by decision. It seeds **synthetically** and is explicitly not `blocked_by` the dataset chain.
- **#544** — **closed `NOT_PLANNED`**, split 2026-10-03. Its children are **#562** (commit the Strong export — closed `COMPLETED`; `test/support/fixtures/strong_workouts.csv`, 1,940,446 bytes) and **#563** (the loader — open). Pass 2's AC 15 named #544 three times; corrected in pass 3.

---

> **Path correction — 2026-09-30.** Flows live at **`integration_test/flows/<flow>_test.dart`**, not `e2e/flows/`. **Proven by experiment:** `flutter test` decides whether a file is an integration test **solely** by whether its path starts with `<project>/integration_test` (`flutter_tools/lib/src/commands/test.dart:888-902`, constant at `:34`), and only then does it request a device (`:621`). The identical test file under `e2e/` ran as a plain **widget** test — exit 0, *"All tests passed!"*, no device requested, asserting nothing about a real app; under `integration_test/` it correctly exited 1 with *"No devices are connected"*. #249's D-2 chose `e2e/` and called the name *"load-bearing, not cosmetic"* — right instinct, wrong conclusion. **D-2's goal survives:** a bare `flutter test` was verified to load only `test/`, ignoring `integration_test/`, so it stays outside the swept tree exactly as `e2e/` would have. Only the name changes. #249 and #415 are closed and stay archival; **#549** owns the substrate.
>
> **CI job ownership — decided 2026-09-30; owner renumbered 2026-10-01.** **#554 builds the e2e CI job itself** — emulator provisioning, `adb reverse tcp:54321 tcp:54321`, and both sets of dart-defines — because that work is inseparable from making the substrate run. There is no emulator-in-CI precedent in any of the 9 workflows, so it is greenfield. **This story keeps ownership of *when* suites fire and of `dart_test.yaml`**: its AC "`ci.yml` implements the decision" means the triggers and selection, not that job's provisioning.
>
> ⚠️ **The owner was #549 when this was written.** #549 was split on 2026-10-01 into **#554** (infrastructure: directory, device binding, `adb reverse`, the CI job, config paths) and **#555** (the entitlement and app-state fixture). The CI job went to #554, whose own negative AC states the reciprocal boundary: *"Does not create `dart_test.yaml` (#413 owns it) … does not decide **when** the suite fires."* Verified 2026-10-01.


