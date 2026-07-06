# Interface / Contract

> **Type**: template

## When to use

Scaffold an interface when the task requires defining a contract between layers — repository interfaces, service contracts, or any abstraction boundary. An interface enables dependency inversion and testability without coupling to implementations.

## File locations

| File | Path |
|---|---|
| Interface | `<data layer>/<feature>/I<Name>Repository.<ext>` |
| Implementation | `<data layer>/<feature>/<Name>Repository.<ext>` |
| Test | `<test tree>/<feature>/<Name>RepositoryTests.<ext>` |

Adapt paths to the project's structure (per `.omp/agent-config.md` § Layer Boundaries). Service interfaces follow the same pattern under the services area.

## Dependencies

- Interface: domain models and types only — no framework or infrastructure imports.
- Implementation: data sources / external clients injected via constructor.

## Template

Use the active pack's `scaffold-snippets.md` (§ Interface / contract) for the concrete idiom. Shape:

```
// Interface: the contract, named with the project's interface convention (e.g. INameRepository)
//   - one focused method per operation (findById, findAll, insert, update, delete)
//   - returns DOMAIN types, never data-layer types

// Implementation: a class implementing the interface
//   - dependencies (data source, remote client, mapper, logger) injected via constructor
//   - private readonly fields per the conventions skill's member order
```

## Wiring

Bind the interface to its implementation in the DI container (per `.omp/agent-config.md` § Pattern Compliance). Consumers depend on the interface, never the implementation directly.

## Conventions

- Interface names follow the project's convention (e.g. `IUserRepository`, `IAuthService`).
- Interfaces live at the layer boundary — domain interfaces in the domain layer, data interfaces in the data layer.
- Keep interfaces focused — prefer multiple small interfaces over one large one.
- Return domain types, not data-layer types.
- No framework imports in the interface or domain models.

## Tests

- Test the implementation against the interface contract.
- Each interface method should have at least one test.
- Mock the interface (with the project's mocking library) in tests for consumers.
- Assert the implementation satisfies the interface type to catch contract violations.
