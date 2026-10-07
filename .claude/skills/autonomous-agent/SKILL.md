---
name: autonomous-agent
description: Shared preamble for autonomous Phase-3 agents — autonomy rules, file-I/O rules, LSP-first code intelligence, ast_grep/ast_edit for structural edits, irc whisper handling, contradiction-exit emission. Loaded by test, ui-story, scaffold, verify, review, create-prd, generate-tasks, self-improve, supervisor, test-preflight.
disable-model-invocation: true
---

# Autonomous Agent Preamble

You are an autonomous agent spawned by the `/cycle` orchestrator. The rules below apply to you regardless of role. Your role-specific responsibilities live in your agent prompt; this skill defines the cross-cutting protocol.

---

## Autonomy

- You receive your task context in the spawn prompt. The user is **not** present — do not ask questions, do not pause for confirmation, do not block on missing context. If context is genuinely insufficient, return early with a clear statement of what is missing.
- You report at the end via a structured return value. Intermediate progress is not surfaced to the user; rely on the event log + cycle state for traceability.

## File I/O

- Use the `Write` / `Edit` / `Read` tools for all file operations.
- **Never** use `python`, shell scripts, `cat <<EOF` heredocs, or `echo >` redirection for file I/O. These bypass the tool layer and break telemetry, hooks, and audit trails.
- Never hand-edit generated files (anything produced by a codegen/build step — e.g. `*.g.dart`, `*.freezed.dart`, or another stack's output such as `*.g.cs`). Re-run the project's **Code generation** command (`.omp/agent-config.md` § Project Commands) instead when codegen output needs updating.

## Skill resolution

Your agent prompt names skills to load (`test-rubric`, `project-conventions`, and so on). How
they reach you differs by harness: omp autoloads them from `autoloadSkills:`, while a Claude
Code subagent gets no autoload and must read the file itself. Assume nothing is preloaded.

To load a named skill, read the first path that exists, in this order:

1. `.claude/skills/<name>/SKILL.md` — relative to your working directory (a Phase-3 worktree
   usually does **not** have this; try it anyway, a deployment may symlink it in)
2. `<repo-root>/.claude/skills/<name>/SKILL.md` — the main checkout, when you are in a worktree
3. `~/.claude/skills/<name>/SKILL.md` — user-scope skills; in a framework deployment this is
   commonly a symlink to the framework checkout and is the path that actually resolves

**A skill you cannot read is a missing gate, not a missing convenience.** Never apply a named
skill "from memory" and continue as though it ran — the rubric you half-remember is not the
rubric, and the run report will record a check that never happened. If a skill your prompt
names as a gate is unreachable at all three paths, stop and emit a `contradiction-exit` block
(schema in `contradiction-exit`) with `trigger: skill-unreachable` and the paths you tried.
For a skill that is advisory rather than a gate, proceed and state plainly in your return that
it was unreachable and which one.

---

## Code intelligence (LSP-first)

When you need to find definitions, references, or rename symbols, prefer the **`lsp`** tool over `grep`:
- `lsp(action: "definition", ...)` — jump to a symbol's definition (more accurate than grepping for the name).
- `lsp(action: "references", ...)` — find all call sites of a symbol (catches shadowed names grep misses).
- `lsp(action: "rename", ...)` — rename a symbol across all files (safer than find-and-replace; never drops callsites).
- `lsp(action: "diagnostics", ...)` — get errors/warnings for a file or glob (use after edits to catch issues early).

Use `grep` only for plain-text lookup when structure is irrelevant (string literals, comments, config keys).

For structural code search and codemods (pattern-based, not text-based), prefer **`ast_grep`** (find) and **`ast_edit`** (rewrite) over manual grep+edit:
- `ast_grep` finds nodes by AST shape — e.g., all calls to `foo($x)` regardless of argument names.
- `ast_edit` rewrites structurally — e.g., `oldApi($A, $B)` → `newApi($B, $A)` with capture substitution.
- Use these when the pattern is syntactic (calls, imports, declarations); use `grep` when it's lexical.

## Whisper handling (Phase-3 implementation agents)

If your role implements code in a worktree (`test`, `ui-story`, `scaffold`, `coding`), supervisor whispers arrive via **irc** as `irc:incoming` turns at your next step boundary — no file polling. Drain your irc inbox (`irc(op: "inbox")`) between sub-tasks and major steps to catch any pending whispers. `pause`-severity whispers are binding; `note` and `strong` are advisory. Report whispers seen and your response in your final summary. Full protocol: `whispers` skill.

Non-implementation agents (`verify`, `review`, `create-prd`, `generate-tasks`, `self-improve`, `monitor`, `supervisor`, `test-preflight`) do not receive whispers — they run too briefly or have orthogonal responsibilities.

## Contradiction-exit emission

If you encounter incompatible sources of truth that cannot be reconciled within your task scope, emit a structured `contradiction-exit` block instead of guessing or thrashing. Full schema: `contradiction-exit` skill. The orchestrator routes contradiction-exit returns directly to L4 (block + surface to user), so do not use this signal for ordinary blockers — use it only when you have genuinely exhausted what your retry cap allows.

## Deviations

If you proceed but diverge from the literal PRD AC or task description (e.g., a different impl shape that satisfies the same AC, a deletion the pre-flight classifier recommended), record a `deviation:` line in your final report:

```
deviation: task: [task-id] | ac: [AC ref or "n/a"] | implemented: [what] | reason: [why]
```

**Design choices are deviations too.** Matching the AC text is not the test — a task can satisfy
every word of its AC and still resolve a decision the AC never addressed. Before writing
`Deviations: None`, check whether you made a call about:

- **Placement** — which layer, class, or module the logic landed in; inside vs. outside an
  existing transaction, lock, or error boundary.
- **Ordering** — where in a sequence the new step runs, and what that implies if a later step
  fails.
- **Boundary** — what the change treats as its own responsibility versus the caller's;
  validation moved to or from an edge.
- **Shape** — a new abstraction, parameter, or field the AC did not ask for.

If you described the choice anywhere in your own prose, it is a deviation — write it as one.
The AC is silent on these by construction, so nothing downstream will catch them: an agent that
put a guard outside a transaction described exactly that placement in its summary and still
reported `Deviations: None`, and only the orchestrator reading the diff caught it. Use
`ac: n/a` when no criterion governs the choice; that is the normal case here, not a reason to
omit the line.

---

## What this preamble does NOT cover

- Role-specific steps and rubrics — those live in your agent prompt and the skills loaded there.
- The Phase-3 escalation ladder — that's orchestrator-side, not agent-side.
- Stall salvage — also orchestrator-side; you do not detect your own stall.
