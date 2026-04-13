# Use Case

> **Type**: template

## When to use

Scaffold a use case when the task describes a single business operation as a verb phrase (e.g., "create workout", "transfer funds", "send notification"). Use cases encapsulate one action with its validation, orchestration, and error handling.

## File locations

| File | Path |
|---|---|
| Use case | `src/domain/<feature>/use-cases/<name>.use-case.ts` |
| Interface (optional) | `src/domain/<feature>/use-cases/<name>.use-case.interface.ts` |
| Test | `test/domain/<feature>/<name>.use-case.test.ts` |

Adapt paths to the project's existing directory structure.

## Dependencies

- Repository interfaces (never implementations directly)
- Other use cases (for composition)
- Domain services (for shared domain logic)
- Injected via constructor

## Template

```typescript
export interface <Name>UseCaseParams {
  // input parameters
}

export interface <Name>UseCaseResult {
  // return type
}

export class <Name>UseCase {
  constructor(
    private readonly someRepository: ISomeRepository,
    // other dependencies
  ) {}

  async execute(params: <Name>UseCaseParams): Promise<<Name>UseCaseResult> {
    this.validate(params);
    // orchestration logic
  }

  private validate(params: <Name>UseCaseParams): void {
    // input validation — throw domain errors for invalid input
  }
}
```

## Wiring

Register in the project's DI container or module system. The use case depends on repository interfaces, not implementations.

## Conventions

- One public method: `execute()` (or a descriptively named method if `execute` is ambiguous)
- Dependencies injected via constructor, stored as private readonly fields
- No framework imports — domain layer is pure TypeScript
- Calls repositories/services via interfaces, never data sources directly
- Throws domain-specific errors, not generic errors

## Tests

- Test happy path with expected inputs
- Test validation (invalid inputs produce domain errors)
- Test edge cases (empty, boundary values)
- Mock repository dependencies at the interface level
