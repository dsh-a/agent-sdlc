# Strategy Pattern

> **Type**: template

## When to use

Scaffold a strategy when the task requires interchangeable algorithms or behaviors — different calculation methods, validation rules, sync strategies, or any family of behaviors selected at runtime. Common for export formats, notification channels, pricing engines, or auth providers.

## File locations

| File | Path |
|---|---|
| Strategy abstraction | `<domain layer>/<feature>/Strategies/I<Name>Strategy.<ext>` |
| Concrete strategy | `<domain layer>/<feature>/Strategies/<Variant><Name>Strategy.<ext>` |
| Context (consumer) | `<domain layer>/<feature>/<Feature>Service.<ext>` |
| Test | `<test tree>/<feature>/Strategies/<Variant><Name>StrategyTests.<ext>` |

Adapt paths to the project's structure (per `.omp/agent-config.md` § Layer Boundaries).

## Dependencies

- Strategy abstraction: domain types only — no framework imports.
- Concrete strategies: may depend on services/configs depending on the variant.
- Context: depends on the abstraction, not concrete implementations.

## Template

Use the active pack's `scaffold-snippets.md` for the concrete idiom. Shape:

```
// Abstraction: I<Name>Strategy with a single execute(input) -> output method.
// Concrete strategies: one class per variant, each implementing the abstraction,
//   stateless where possible.
// Context/consumer: depends on the abstraction; may allow swapping the strategy;
//   delegates work to the injected strategy.
```

## Wiring

Register concrete strategies in the DI container (per `.omp/agent-config.md` § Pattern Compliance). The context receives a strategy via constructor injection or a factory that selects the appropriate strategy at runtime (e.g. based on configuration).

## Conventions

- All strategies implement the same abstraction — they are fully interchangeable.
- Strategy selection logic lives outside the strategies (factory, config, or context).
- Concrete strategies are stateless where possible.
- Each strategy is independently testable in isolation.
- No framework imports in domain strategies.
- Use the project logger in the context/consumer, not in individual strategies unless complex.

## Tests

- Test each concrete strategy independently.
- Test the context with different strategies to verify interchangeability.
- Test strategy selection logic (factory or config-based selection).
- Each strategy should produce distinct, verifiable output for the same input.
