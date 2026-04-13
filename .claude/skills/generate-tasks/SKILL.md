# Generate Tasks

You are generating a task list from a PRD.

PRD file: **$ARGUMENTS**

If $ARGUMENTS is empty, ask the user to provide the path to a PRD file (e.g. `agent_tasks/prd-feature-name.md`).

## Output

- **Format**: Markdown (.md)
- **Location**: `/agent_tasks/`
- **Filename**: `tasks-[prd-file-name].md` (e.g., `tasks-prd-user-alarm.md`)

## Process

1. **Receive PRD Reference**: Read the specified PRD file.

2. **Analyze PRD**: Read and analyze the functional requirements, user stories, and other sections.

3. **Assess Current State**: Review the existing codebase to understand architectural patterns and conventions. Identify existing components, files, and utilities that can be leveraged or need modification.

4. **Phase 1 — Generate Parent Tasks**: Based on the PRD analysis and current state, create the main high-level tasks (likely around 5). Present these to the user in the format below (without sub-tasks yet). Inform the user: "I have generated the high-level tasks based on the PRD. Ready to generate the sub-tasks? Respond with 'go' to proceed."

5. **Wait for Confirmation**: Pause and wait for the user to respond with "go".

6. **Phase 2 — Generate Sub-Tasks**: Break down each parent task into smaller, actionable sub-tasks. Ensure sub-tasks:
   - Logically follow from the parent task
   - Cover the implementation details implied by the PRD
   - Consider existing codebase patterns

7. **Identify Relevant Files**: Based on the tasks and PRD, list files that will need to be created or modified, including corresponding test files.

8. **Generate Final Output**: Combine parent tasks, sub-tasks, relevant files, and notes into the final Markdown structure.

9. **Review and Improve**: Before saving, critically review the task list for:
   - **Validation steps**: Missing validation or error-checking tasks?
   - **Scope creep**: Any tasks too complex that should be simplified?
   - **Error handling**: Proper error handling tasks?
   - **Testing gaps**: Integration or end-to-end tests needed beyond unit tests?
   - **Task granularity**: Tasks too granular (combine) or too broad (split)?
   - **Edge cases**: Missing tasks for edge cases or special scenarios?

   Present findings with suggested improvements, prioritized by importance (high/medium/low). Ask if the user wants to incorporate changes before finalizing.

10. **Save Task List**: Save in `/agent_tasks/` with filename `tasks-[prd-file-name].md`.

## Output Format

```markdown
## Relevant Files

### Source Files (modify)
- `src/path/to/file.ts` — Brief description of why this file is relevant

### Source Files (create)
- `src/path/to/new-file.ts` — Brief description

### Test Files (create)
- `test/path/to/file.test.ts` — Tests for `file.ts`

### Notes
- Unit tests go in `test/` mirroring the source structure
- Component tests go in `test/` mirroring the UI structure
- Use `npm test` to run tests (or `npm test -- [optional/path]` for specific files)

## Tasks

- [ ] 1.0 Parent Task Title
    - [ ] 1.1 Sub-task description
    - [ ] 1.2 Sub-task description
- [ ] 2.0 Parent Task Title
    - [ ] 2.1 Sub-task description
- [ ] 3.0 Parent Task Title (may not require sub-tasks if purely structural)
```

## Interaction Model

1. **After Parent Tasks (Phase 1)**: Pause for user confirmation before generating sub-tasks.
2. **After Task Generation (Phase 2)**: Present a critical review with potential improvements. Wait for user feedback before finalizing and saving.

## Target Audience

Assume the primary reader is a **junior developer** who will implement the feature with awareness of the existing codebase context.
