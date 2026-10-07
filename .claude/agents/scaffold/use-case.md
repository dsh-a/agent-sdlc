# Use Case

> **Type**: template
> **Category**: architecture
> **Triggers**: use case, interactor, business operation, verb phrase, application service, single action
> **Related**: command, facade, service, interface

## Intent

Encapsulate a single business operation — its validation, orchestration, and error handling — as one unit that is independent of both the UI and the infrastructure.

## When to use

Scaffold a use case when the task describes a single business operation as a verb phrase (e.g. "create workout", "transfer funds", "send notification"). Use cases encapsulate one action with its validation, orchestration, and error handling.

- The task names an action the system performs on behalf of a user or another system.
- Business rules govern whether and how the action proceeds, and those rules belong to the domain rather than to a screen or a controller.
- The operation coordinates repositories, services, or other use cases to reach one outcome.

**Not when:**
- The operation is a pass-through to a single repository method with no rules. Call the repository; `minimalism` forbids the ceremony.
- The work is providing a capability rather than deciding something → `service.md`.
- The work is aggregating several operations into a feature-level API for consumers → `facade.md`.
- The request must be queued, logged, retried, or undone as an object → `command.md`, which adds those capabilities on top of the same idea.

## Participants

| Role | Responsibility | Path |
|---|---|---|
| Use case | Validates input, orchestrates dependencies, returns a result or raises a domain error | `<domain layer>/<feature>/UseCases/<Name>UseCase.<ext>` |
| Params / Result | The operation's input and output types, in domain terms | `<domain layer>/<feature>/UseCases/<Name>UseCase.<ext>` (co-located) |
| Interface (optional) | The contract, when the use case must be substitutable | `<domain layer>/<feature>/UseCases/I<Name>UseCase.<ext>` |
| Consumer | The presentation layer, a facade, or another use case | UI / presentation layer |
| Test | Verifies happy path, validation, edge cases, and dependency failure | `<test tree>/<feature>/UseCases/<Name>UseCaseTests.<ext>` |

Adapt paths to the project's structure (per `.omp/agent-config.md` § Layer Boundaries).

### Structure

```
  Consumer ──▶ <Name>UseCase.execute(params)
                    │ 1. validate  → domain error on bad input
                    │ 2. orchestrate → repositories / services / other use cases
                    └ 3. return result
   (depends on INTERFACES only; never on data sources or frameworks)
```

**Collaborations:** the consumer supplies params and receives a result or a domain error. The use case calls repository and service interfaces, and never touches a data source, an SDK, or the UI.

## Dependencies

- Repository interfaces (never implementations directly)
- Other use cases (for composition)
- Domain services (for shared domain logic)
- Injected via constructor

## Template

Use the active pack's `scaffold-snippets.md` for the concrete idiom. Shape:

```
// Params: <Name>UseCaseParams — the input, in domain types.
// Result: <Name>UseCaseResult — the output, in domain types.
// Use case: <Name>UseCase with ONE public method, execute(params) -> result.
//   - dependencies injected via constructor, stored as private readonly fields
//   - private validate(params) runs first and raises domain errors for bad input
//   - then orchestration: call repository/service INTERFACES and combine results
//   - throws domain-specific errors, never generic ones
```

## Wiring

Register in the project's DI container or module system. The use case depends on repository interfaces, not implementations. Consumers resolve the use case (or its interface) and call it; a use case must never be constructed inline with concrete dependencies, which would weld the domain to the data layer.

## Conventions

- One public method: `execute()` (or a descriptively named method if `execute` is ambiguous).
- Dependencies injected via constructor, stored as private readonly fields.
- No framework imports — the domain layer stays pure.
- Calls repositories/services via interfaces, never data sources directly.
- Throws domain-specific errors, not generic errors.
- Validation happens before any side effect, so a rejected request leaves no partial state.
- The use case holds no state between calls.
- Named as a verb phrase matching the operation it performs.

## Tests

- Test happy path with expected inputs.
- Test validation (invalid inputs produce domain errors) and assert **no** repository call was made on rejection.
- Test edge cases (empty, boundary values).
- Test dependency failure — a repository or service raises, and the use case surfaces a domain error.
- Mock repository dependencies at the interface level.
- Test orchestration order where one call depends on another's result.

## Consequences

1. **One operation, one file, one reason to change.** The business rule for an action has a single home, findable by its name, testable without a UI or a database.
2. **The domain stays independent.** Because the use case depends only on interfaces, the same operation serves any UI and any storage backend.
3. **Composable.** Use cases call other use cases, so larger operations are assembled from verified smaller ones rather than duplicated.
4. **Cost: a class per operation.** A system with many small operations accumulates many small files, and a use case that only forwards to a repository is pure overhead — which is exactly what the *Not when* list above exists to prevent.
