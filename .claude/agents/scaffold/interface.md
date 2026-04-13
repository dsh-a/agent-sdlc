# Interface / Contract

> **Type**: template

## When to use

Scaffold an interface when the task requires defining a contract between layers or modules — repository interfaces, service contracts, port definitions, or any abstraction boundary. Interfaces enable dependency inversion and testability.

## File locations

| File | Path |
|---|---|
| Interface | `src/<layer>/<feature>/<name>.interface.ts` |
| Implementation | `src/<layer>/<feature>/<name>.ts` |
| Test (implementation) | `test/<layer>/<feature>/<name>.test.ts` |

Adapt paths to the project's existing directory structure.

## Dependencies

- Domain types and models only (interfaces should not depend on infrastructure)

## Template

```typescript
// --- Interface definition ---

export interface I<Name> {
  findById(id: string): Promise<<Entity> | null>;
  findAll(filter?: <Filter>): Promise<<Entity>[]>;
  create(data: Create<Entity>Dto): Promise<<Entity>>;
  update(id: string, data: Update<Entity>Dto): Promise<<Entity>>;
  delete(id: string): Promise<void>;
}

// --- Implementation ---

export class <Name> implements I<Name> {
  constructor(
    // infrastructure dependencies
  ) {}

  async findById(id: string): Promise<<Entity> | null> {
    // implementation
  }

  // ... remaining methods
}
```

## Wiring

Bind the interface to its implementation in the DI container. Consumers import and depend on the interface, never the implementation directly.

## Conventions

- Interface names use `I` prefix (e.g., `IUserRepository`) or project convention
- Interfaces live at the layer boundary — domain interfaces in domain, infrastructure interfaces in infrastructure
- Keep interfaces focused — prefer multiple small interfaces over one large one (Interface Segregation)
- Return domain types, not infrastructure types (e.g., return `User`, not `UserRow`)

## Tests

- Test the implementation against the interface contract
- Each interface method should have at least one test
- Use the interface type for the variable in tests to catch contract violations at compile time
