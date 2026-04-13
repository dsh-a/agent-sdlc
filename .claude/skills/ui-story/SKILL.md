# UI Story

You are about to work on a UI feature. Before writing any code, complete the following steps in order.

## Step 1 — Load design context

Read the design context file:
@documentation/DESIGN.md

## Step 2 — Load architecture context

Read the **Pattern Compliance** and **Layer Boundaries** sections in `.claude/config.md` for project-specific UI architecture rules.

General UI rules (apply unless config specifies otherwise):
- Components call state management layer only — never repositories, services, or data sources directly
- Use the project's design token / theme system — never hardcoded styles
- Break large render methods into small, focused sub-components
- Never perform network calls or heavy computation inside render paths
- Use virtualized lists for any list longer than a handful of static items

## Step 3 — Understand the task

The UI story to work on: **$ARGUMENTS**

If $ARGUMENTS is empty, ask the user to describe:
1. What screen or component are we building or modifying?
2. What is the user trying to accomplish on this screen?
3. Are there any existing related views or ViewModels to check for consistency?

## Step 4 — Gather acceptance criteria

Search `agent_tasks/` for the PRD or story that governs this UI work:
- Extract the functional requirements and acceptance criteria relevant to this view
- These drive what the UI must do — not just what it looks like

If no PRD exists, ask the user for the acceptance criteria before proceeding.

## Step 5 — Explore before building

Before writing any code:
- Find and read any existing related UI components or state management files for this feature area
- Check for existing theme system, design tokens, and shared styles
- Check for reusable shared components
- Determine whether state management (store, view model, hook, etc.) already exists or needs to be created
- Check the routing configuration to determine if a new route is needed

## Step 6 — Propose before implementing

Summarize your plan in plain language:
- What the screen/component will look like and why (reference design principles where relevant)
- What components/elements you'll use for structure (and what you're deliberately avoiding)
- Whether you're using a modal, drawer, inline expansion, or other pattern — and why
- Any new state management methods or state needed
- How the acceptance criteria from Step 4 will be satisfied by this UI

Wait for user approval before writing code.

## Step 7 — Implement

Follow these conventions:

### State management (if creating/modifying)

Follow the project's state management pattern as declared in `.claude/config.md` (Pattern Compliance section). General conventions:

- Dependencies via constructor or injection — never import data sources directly
- Expose state via getters or observable properties (loading, error, data)
- Expose actions as public methods
- Use the project's logger, never `console.log` in production code
- Follow class member order from CLAUDE.md or project conventions

### UI component
- Use the project's state consumption pattern (hooks, selectors, context, subscriptions)
- Use the project's theme/design token system — never hardcoded styles
- Break large render methods into small sub-components when they exceed ~40 lines
- Use test-friendly identifiers (data-testid, aria-label, etc.) on elements that need to be found in tests
- Handle loading and error states explicitly

### File locations

Follow the project's existing directory structure. If no convention exists, use a feature-based layout:
- State: `src/<feature>/state/` or `src/<feature>/stores/`
- Component: `src/<feature>/components/` or `src/<feature>/views/`
- Route: project routing config
- DI/wiring: project DI config

## Step 8 — Write component tests

Every component created or significantly modified must have tests. Do not skip this step.

### Required coverage

For each component, write tests that verify:

1. **Renders correctly** — key elements are present in the initial state (text, buttons, inputs)
2. **Loading state** — if the component has a loading state, verify it shows the loading indicator and disables interactions
3. **Error state** — if the component has an error state, verify the error message is displayed
4. **User interactions** — click buttons, enter text, toggle switches — verify the correct handlers or state changes are triggered
5. **AC-driven tests** — for each UI-relevant acceptance criterion from Step 4, write a test that verifies the criterion through the rendered output

### Snapshot tests

For components with significant visual design (not simple forms), write a snapshot test. Present the update command to the user — **never auto-update snapshots without user review**.

### Test file location

Tests should mirror the source structure. Follow the project's existing test layout convention.

### Patterns

- Render the component with necessary providers, stores, or context — reuse shared test helpers where possible
- Wait for async operations to settle after interactions
- Use test-friendly selectors (data-testid, aria roles, text content) for precise element selection
- Mock state management for isolated component tests; use real state with mocked dependencies for integration-style tests

## Step 9 — Verify

- Run `npm run typecheck && npm run lint`
- Run the tests: `npm test -- <test_file_path>`
- If snapshot tests were created, remind the user to review the snapshots
- Confirm the acceptance criteria from Step 4 are satisfied
