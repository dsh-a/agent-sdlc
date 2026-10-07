# Harness findings — myapp cycle something (#562)

**Date**: 2026-10-03

## P0 — Worktree base bug: reported 2026-08-24, still live

Filed six weeks ago as P0. Unfixed.
**Proposed:** pass the base to worktree creation.

### P0a — and isolation is structurally wrong for untracked inputs

`git worktree add` materialises tracked content only.

## What worked, and must not be "fixed"

- The isolated-agent base check.
