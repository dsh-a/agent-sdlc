---
name: minimalism
description: The reuse-first / YAGNI ladder for implementation agents. Enforces the smallest change that actually works — reuse before write, stdlib before custom, native before dependency, one line before fifty — after the problem is understood, never instead of understanding it. Language-neutral; concrete idioms come from the active pack and `project-conventions`. Loaded by coding, ui-story, scaffold, and generate-tasks.
disable-model-invocation: true
---

# Minimalism

The best code is the code never written. Lazy means efficient, not careless — you have been paged at 3am for an over-engineered codebase. This rule governs **what you build**, not how much you read: it shortens the solution, never the comprehension.

This is a language-neutral skill. `project-conventions` and the active pack (`.claude/config.md` → **Active Pack**) own the concrete idioms — standard-library names, native platform features, the dependency manifest, the comment syntax. This skill owns the reflex.

Load-bearing constraint: the ladder runs **after** you understand the problem. Read the task and the code it touches, trace the real flow end to end, *then* climb. The smallest change in the wrong place isn't lazy — it's a second bug.

---

## The ladder

Stop at the first rung that holds. Two rungs work → take the higher one and move on.

1. **Does this need to exist at all?** Speculative need = skip it, say so in one line. (YAGNI)
2. **Already in this codebase?** A use case, service, component, helper, extension, or type that already lives here → reuse it. Look before you write — re-implementing what's a few files over is the most common slop. (This is the same instinct `pattern-divergence` enforces for tests: honor what's already there.)
3. **Standard library does it?** Use the language's stdlib / core collections before hand-rolling. (The active pack names the idioms.)
4. **Platform / framework-native feature covers it?** A framework capability or built-in control over a dependency or hand-rolled code (a native UI control over a widget lib, a DB constraint over app-code validation, a language feature over a utility).
5. **A dependency already in the project's manifest solves it?** Use it. **Never add a new dependency for what a few lines can do** — and never add one without checking the manifest first (per global workflow rules).
6. **Can it be one line?** One line.
7. **Only then:** the minimum code that works.

## Bug fix = root cause, not symptom

A report names a symptom. Before you edit, grep every caller of the function you are about to touch. The lazy fix **is** the root-cause fix: one guard in the shared function is a smaller diff than a guard in every caller — and patching only the path the ticket names leaves every sibling caller still broken. Fix it once, where all callers route through.

## Rules

- No unrequested abstractions: no interface with one implementation, no factory for one product, no config for a value that never changes. (Layer-boundary interfaces that `project-conventions` *requires* at seams are not this — those are requested.)
- No boilerplate or scaffolding "for later." Later can scaffold for itself.
- Deletion over addition. Boring over clever — clever is what someone decodes at 3am. Fewest files possible; shortest working diff wins, once you understand the problem.
- Two stdlib options, same size? Take the one that's correct on edge cases. Lazy means writing less code, not picking the flimsier algorithm.
- Complex request you can't fully satisfy small? Ship the lazy version and flag it in the same report: "Did X; Y covers it. Need full X? Say so." Never stall on an answer you can default.

## Mark deliberate simplifications

When you take a shortcut with a known ceiling (global lock, O(n²) scan, naive heuristic, a case not yet handled), leave one comment naming the ceiling and the upgrade trigger, using the language's comment syntax:

```
// minimalism: linear scan, index this if the collection grows past a few hundred
# minimalism: handles the single-account case; loop when multi-account lands
```

The marker reads as intent, not ignorance, and keeps a deferral from silently rotting into "later means never." Trivial one-liners need no comment.

## When NOT to be lazy

Never simplify away, no matter the intensity:

- **Understanding the problem.** The ladder shortens the diff, never the reading. A small diff you don't understand is laziness dressed up as efficiency — it ships a confident wrong fix. Read fully, then be lazy.
- **Input validation at trust boundaries** (user input, network, deserialization).
- **Error handling that prevents data loss** — async work at system boundaries (database, HTTP, external services) keeps its error handling. (Internal trusted-layer code still doesn't need defensive noise — that distinction is `project-conventions`', not a license to drop real boundary handling.)
- **Security** — auth, user data, credentials, injection surfaces.
- **Accessibility basics** — where the platform has them (labels, focus/tap targets, contrast).
- **Entity/model construction correctness.** `project-conventions` § Entity / model construction owns this: assign every field explicitly, cross-check the field list, use the project's copy/`with` idiom for mutations. "Fewer lines" never overrides it.
- **Required tests.** The pipeline's test coverage is not bloat to cut. Minimalism reduces the code under test, not the tests the AC demands.
- **Anything explicitly requested.** User or AC asked for the full version → build it, no re-arguing.

---

## What this skill does NOT cover

- **Intensity levels.** This pipeline runs one fixed default (the full ladder). There is no lite/ultra toggle — an autonomous agent has no user mid-task to pick a level.
- **Over-engineering *review*.** Flagging complexity in already-written code is `minimalism-review` (loaded by the review agent), not this skill. This one governs code as you write it.
- **A debt ledger.** The `minimalism:` comments are a local record, not a harvested report.
- **Language idioms.** Which stdlib call, which native control, which manifest — that's `project-conventions` and the active pack, not this skill.
