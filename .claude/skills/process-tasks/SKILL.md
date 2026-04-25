# Process Task List (Manual Mode)

> **Note:** This skill is the manual, step-by-step mode of the `/cycle` pipeline. You can invoke it directly or via `/cycle --manual [task-file]`. For autonomous execution with parallel agents, state persistence, and error recovery, use `/cycle` (without `--manual`) instead.

You are implementing tasks from a task list in **manual mode** — you pause after every sub-task for user approval.

Task file: **$ARGUMENTS**

If $ARGUMENTS is empty, ask the user to provide the path to a task file (e.g. `agent_tasks/tasks-prd-feature-name.md`).

---

## Before starting

1. Read the task file and identify the next incomplete sub-task
2. Read the PRD referenced by the task file to understand acceptance criteria
3. Check `agent_states/` for an existing cycle state file for this feature — if found, inform the user and ask whether to resume via `/cycle` instead

---

## Task implementation

- **One sub-task at a time**: Do **NOT** start the next sub-task until you ask the user for permission and they say "yes" or "y".

- **Completion protocol**:

    i. When you finish a sub-task, immediately mark it as completed by changing `[ ]` to `[x]`.

    ii. If all sub-tasks underneath a parent task are now `[x]`, follow this sequence:
        - **First**: Run the full test suite (`flutter test`), pause and notify the user of the results: "Tests passed" or "Tests failed" before proceeding.
        - **Only if all tests pass**: Stage changes (`git add` with specific files — not `git add .`)
        - **Clean up**: Remove any temporary files and temporary code before committing
        - **Commit**: Use conventional commit format (`feat:`, `fix:`, `refactor:`, etc.) that summarizes the parent task, lists key changes, and references the task number and PRD context.

    iii. Once all sub-tasks are marked completed and changes have been committed, mark the **parent task** as completed.

- Stop after each sub-task and wait for the user's go-ahead.

### Skill delegation during implementation

When a sub-task matches one of these patterns, apply the corresponding skill's logic:

- **Creating a new domain entity/model end-to-end**: follow the conventions from `/scaffold`
- **Writing or updating tests**: follow the conventions from `/test` (gather AC from PRD, cross-reference implementation, anti-faking checks, boundary tests)
- **Building or modifying UI**: follow the conventions from `/ui-story` (read design context, check theme, propose before building)

You do not need to invoke these skills literally — apply their logic and conventions inline as you work.

### Error recovery

In manual mode, you don't have the full escalation ladder. If a sub-task fails:
1. Attempt to fix it yourself (one retry)
2. If the fix doesn't work, report the error to the user with context and wait for guidance

---

## Task list maintenance

1. Update the task list as you work:
    - Mark tasks and sub-tasks as completed when done (`[x]`) per the protocol above.
    - Add new tasks as they emerge.
2. Keep "Relevant Files" accurate and up to date.
3. Before starting work, check which sub-task is next.
4. After implementing a sub-task, update the file and then pause for user approval.
