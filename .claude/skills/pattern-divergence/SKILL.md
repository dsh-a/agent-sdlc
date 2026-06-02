---
name: pattern-divergence
description: Rule for handling existing test-pattern conventions in a directory. When an agent's preferred pattern differs from the dominant one, it must match, migrate, or declare — never split silently. Generalized from synthesis item 5.4.5; consumed today by the test agent.
disable-model-invocation: true
---

# Pattern Divergence

When you are about to write tests in a directory that already contains tests, **detect the dominant pattern first**. If your default differs, you must choose one of three explicit paths. Never leave the directory in a mixed state with no record of why.

This rule applies to test files. It does not apply to fixtures, helpers, or generated code.

---

## Step 1 — Detect the dominant pattern

Scan the other test files in the same directory (not the broader tree). Identify the dominant convention along these three dimensions:

### A. Mocking library
- A reflection/dynamic mock library (e.g. Moq, NSubstitute, mocktail/mockito) — `Mock<X>`, configured stubs, interaction verification.
- Hand-written fakes/stubs — a concrete fake implementing the interface with hand-written method bodies.

Highest-impact divergence. Mixing a mock library and hand-written fakes in one directory is the canonical 5.4.5 failure case.

### B. Setup pattern
- Shared setup (constructor / `IClassFixture` / `setUp`) declaring the subject and dependencies once.
- Inline construction inside each test.

### C. Async / time style
- Plain `async`/`await` on the system under test.
- A controlled clock / fake time provider for time-sensitive tests.
- Explicit waits / pumps where the UI framework requires draining the event loop.

If the directory has fewer than 2 existing test files, there is no dominant pattern to honor — proceed with your default. Note this in your final report so reviewers know the pattern was set by your work.

---

## Step 2 — Decide

Apply this decision tree in order:

### Match (default)
If the existing pattern works for your task, use it. No deviation needed. Same library, same setup style, same async style.

### Migrate
If you have a **strong reason** to switch (existing pattern cannot express the AC; the library is deprecated; the project is mid-migration with explicit user direction), rewrite **all** existing test files in the same directory in the same commit. Log a `deviation:` summarizing the migration:

```
deviation: task: [task-id] | ac: [n/a — migration] | implemented: migrated mock-library → hand-written fakes across [N files: list] | reason: [strong reason]
```

Migration must be all-or-nothing within the directory. Do not migrate some files and leave others.

### Declare
If migration is out of scope (too many files, risky, or you lack a strong reason but the existing pattern is genuinely awkward for your task), write your new tests in the **existing** pattern even if it's awkward, and log a `deviation:` flagging the awkwardness:

```
deviation: task: [task-id] | ac: [ac-id] | implemented: kept directory's existing mocking pattern despite [specific awkwardness] | reason: migration out of scope for this task
```

This tells verify and the user that the pattern choice was conscious and the awkwardness is known.

---

## Step 3 — Forbidden

Writing new tests in your preferred pattern when an existing pattern is present, **without** migrating or declaring, is a silent split. Reviewers cannot distinguish it from a mistake; future agents have no canonical pattern to follow.

If you find yourself doing this, stop, reread Step 2, and pick a path.

---

## What this does NOT cover

- **Test grouping / structure** (one group per method vs. per behavior) — cosmetic; not flagged.
- **Naming conventions** (`Should_Do_X` vs. `does x`) — match locally but no formal rule.
- **Fixture organization** — handled by the project's shared test-fixture/helper conventions.
- **Patterns across directories** — only the current directory's pattern matters. Different directories may legitimately use different patterns (data-layer manual stubs, presentation-layer mocks).

---

## Verify-side check

Verify's Step 4b (scope-creep audit) reads deviations and the diff. A directory diff that introduces a new mocking library or setup style without a matching `migrated` or `kept` deviation is treated as a silent split — verify flags it as INCOMPLETE.
