---
Globs: test/**
---

# Known Pitfalls — Tests

Project-specific traps. Loaded only when the active edit touches `test/**`.

- **Severity: hard** — wrong here means the test silently passes.
- **Severity: warn** — easy to get wrong; recoverable.

---

## Mocktail mechanics

### Watch out for: `registerFallbackValue` for complex argument types

**Severity: hard**

`when(() => mock.foo(any()))` throws `TypeError` if `T` lacks a registered fallback.

### Watch out for: `verify` after `verifyNever`

**Severity: warn**

Ordering matters; the second call asserts against a cleared log.

## Sync layer

### Watch out for: Drift writes bypass the repository

**Severity: hard**

A direct Drift write skips the syncable layer and never enqueues.
