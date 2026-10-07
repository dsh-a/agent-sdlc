# Interface / Contract

> **Type**: template
> **Category**: architecture
> **Triggers**: interface, contract, abstraction boundary, repository interface, service contract, dependency inversion, port
> **Related**: adapter, proxy, service, strategy

## Intent

Define a contract at a layer boundary so that consumers depend on behaviour rather than on an implementation, inverting the direction of the dependency.

## When to use

Scaffold an interface when the task requires defining a contract between layers — repository interfaces, service contracts, or any abstraction boundary. An interface enables dependency inversion and testability without coupling to implementations.

- A domain-layer consumer needs behaviour that only the data or infrastructure layer can provide. The interface lets the dependency point inward, toward the domain.
- The implementation must be substitutable — a fake in tests, a second backend, a different platform.
- The consumer must be testable without the real dependency present.
- The layer boundary is one the architecture rules already enforce (per `.omp/agent-config.md` § Layer Boundaries).

**Not when:**
- The type has one implementation, is not a layer boundary, and is not mocked in tests. That is an interface for its own sake, and `minimalism` forbids it.
- You are conforming an existing third-party type to your contract — you still need the interface, but the work is `adapter.md`.
- The "interface" would simply mirror one class's every public method. Extract the contract the consumer actually needs instead.

## Participants

| Role | Responsibility | Path |
|---|---|---|
| Interface | The contract, expressed in domain vocabulary and domain types | `<data layer>/<feature>/I<Name>Repository.<ext>` |
| Implementation | Satisfies the contract against a real data source or client | `<data layer>/<feature>/<Name>Repository.<ext>` |
| Consumer | Depends on the interface; never names the implementation | `<domain layer>/<feature>/<Feature>Service.<ext>` |
| Test | Verifies the implementation against the contract, method by method | `<test tree>/<feature>/<Name>RepositoryTests.<ext>` |

Adapt paths to the project's structure (per `.omp/agent-config.md` § Layer Boundaries). Service interfaces follow the same pattern under the services area.

### Structure

```
  domain layer      Consumer ──depends on──▶ «interface» IName
                                                    △
  ────────────────────────────────────────────────  │  ── layer boundary
                                                    │ implements
  data layer                                  NameImplementation ──▶ data source
```

**Collaborations:** the consumer calls the interface; the DI container supplies the implementation at the composition root. The dependency arrow crosses the boundary in the opposite direction to the call.

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

Bind the interface to its implementation in the DI container (per `.omp/agent-config.md` § Pattern Compliance). Consumers depend on the interface, never the implementation directly. The binding is the only place both names appear together.

## Conventions

- Interface names follow the project's convention (e.g. `IUserRepository`, `IAuthService`).
- Interfaces live at the layer boundary — domain interfaces in the domain layer, data interfaces in the data layer.
- Keep interfaces focused — prefer multiple small interfaces over one large one.
- Return domain types, not data-layer types. A leaked DTO or SDK type makes the boundary decorative.
- The interface is written for its **consumer's** needs, not as a mirror of the implementation's surface.
- Errors are part of the contract: state which domain errors a method may raise.
- No framework imports in the interface or the domain models.

## Tests

- Test the implementation against the interface contract.
- Each interface method should have at least one test.
- Mock the interface (with the project's mocking library) in tests for consumers.
- Assert the implementation satisfies the interface type to catch contract violations.
- Where several implementations exist, run one shared contract test suite against each so they stay genuinely substitutable.

## Consequences

1. **Inverts the dependency across a layer boundary.** The domain stops depending on infrastructure, which is what makes the domain independently testable and independently reusable.
2. **Substitutability.** Fakes in tests, a second backend, or a platform-specific implementation all arrive without touching a consumer.
3. **The contract becomes reviewable.** The interface is a small, readable statement of what a layer promises — often the most useful file in a feature.
4. **Cost: indirection, and a contract that can drift.** Every call goes through an abstraction, "go to definition" lands on the interface rather than the code, and an interface that grows to mirror one implementation has stopped paying for itself. Keep it consumer-shaped and small.
