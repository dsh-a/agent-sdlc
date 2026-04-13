# Scaffold

You are scaffolding a new component. This skill supports multiple scaffold types.

The component to scaffold: **$ARGUMENTS**

---

## Step 1 — Determine scaffold type

Inspect $ARGUMENTS to determine what to scaffold. If ambiguous, ask the user.

| Type | Trigger | Example |
|---|---|---|
| **Model / entity** | "entity", "model", or a noun implying a data object | `/scaffold Equipment` |
| **Service** | "service" or infrastructure concern | `/scaffold service Analytics` |
| **Repository** | "repository", "repo", or data access | `/scaffold repo UserRepository` |
| **Controller / handler** | "controller", "handler", "endpoint" | `/scaffold controller WorkoutApi` |
| **UI component** | "view", "screen", "page", "component" | `/scaffold view WorkoutDetail` |

Then jump to the corresponding section below.

---

## Step 2 — Check for conflicts (all types)

Before creating anything:
- Search the project's source directory for existing files with the same name
- If conflicts exist, stop and ask the user whether to extend or rename

---

## Step 3 — Load pattern (priority order, all types)

Check `.claude/agents/scaffold/` for a matching pattern file:

1. **Project-specific pattern** (`Type: project-specific`): Follow it — it reflects this project's actual conventions. Skip the generic sections below.
2. **GoF template** (`Type: template`): Use it as a starting point, but adapt to the project's codebase. The generic sections below provide additional guidance.
3. **No pattern file**: Explore the codebase — find 1-2 existing examples of the same type, read them, extract conventions.

Also read `.claude/config.md` (Architecture Review Rules) for layer boundaries and pattern compliance.

If no project-specific pattern files exist at all, autonomously spawn a setup-scaffold agent before proceeding:

```
Agent(subagent_type: "general-purpose", model: "sonnet",
      prompt: "Run the /setup-scaffold skill in scan mode. Read .claude/skills/setup-scaffold/SKILL.md and follow its steps. Do not ask the user questions — use your best judgment for pattern discovery and create all pattern files you find. Report what was created.")
```

Wait for it to complete, then re-read `.claude/agents/scaffold/` and continue with the pattern matching above.

---

## Model / Entity

### Gather requirements
1. What is the entity name?
2. What fields does it have? (name, type, nullable, default)
3. Does it need persistence? (database table, ORM model)
4. Does it have relationships to other entities?

### Propose the plan

Present the files to create and modify. Wait for user approval before writing code.

### Create the model
- Follow the project's existing model/entity conventions (check for base classes, interfaces, decorators)
- Include standard fields (id, timestamps) matching existing patterns
- Implement any required methods (serialization, validation) matching existing patterns
- Domain/core models should have no framework imports (per config layer boundaries)

### Database / ORM integration (if applicable)
- Create migration, schema, or table definition matching the project's ORM pattern
- Follow existing naming conventions for tables/columns
- Define relationships/foreign keys as needed

### Repository (if applicable)
- Create repository interface and implementation following existing patterns
- Wire into DI / module registration

### Verify
- `npm run typecheck && npm run lint`
- Run codegen if schema was modified (`npm run codegen`)
- List remaining steps (tests, API endpoints, UI)

---

## Service

Services wrap infrastructure concerns (auth, external APIs, platform features).

### Gather requirements
1. What infrastructure concern does this service wrap?
2. What external dependencies does it need?

### Create the service
- Follow existing service patterns in the codebase (class structure, error handling, logging)
- Constructor takes external dependencies via injection
- Public methods expose the operations
- May use framework imports (unlike domain layer)

### Wire into DI
Follow the project's DI / module registration pattern.

### Verify
- `npm run typecheck && npm run lint`
- List remaining steps

---

## Repository

Repositories abstract data access behind interfaces.

### Gather requirements
1. What entity does this repository manage?
2. What data source(s) does it use? (database, API, cache)
3. What operations does it need? (CRUD, custom queries)

### Create the repository
- Create interface/abstract class defining the contract
- Create implementation with data source dependencies
- Follow existing repository patterns in the codebase
- Use proper error handling at data access boundaries

### Wire into DI
Follow the project's DI / module registration pattern.

### Verify
- `npm run typecheck && npm run lint`
- List remaining steps

---

## Controller / Handler

Controllers handle incoming requests and coordinate responses.

### Gather requirements
1. What routes/endpoints does this controller handle?
2. What services or use cases does it depend on?
3. What request/response shapes are needed?

### Create the controller
- Follow existing controller patterns (decorators, middleware, validation)
- Dependencies injected via constructor or framework mechanism
- Input validation at the boundary
- Proper error handling and response formatting

### Wire into routing
Register routes following the project's routing pattern.

### Verify
- `npm run typecheck && npm run lint`
- List remaining steps

---

## UI Component

### Gather requirements
1. What screen or component is this for?
2. What state management does it need?
3. What state does it expose? (loading, error, data)
4. What user actions does it handle?

### Create the component
Follow the project's UI conventions (read `.claude/config.md` Pattern Compliance section):
- State management: follow the project's declared pattern
- Component structure: follow existing component patterns
- Styling: use the project's theme/design token system

### Wire into routing and DI
- Register route if needed
- Wire state management into DI if needed

### Verify
- `npm run typecheck && npm run lint`
- List remaining steps (tests, additional wiring)

---

## Final step (all types)

- Run `npm run typecheck && npm run lint`
- Confirm everything compiles cleanly
- List remaining steps the user needs (tests, additional wiring, database migrations)
