# Strategy Pattern

> **Type**: template

## When to use

Scaffold a strategy when the task requires interchangeable algorithms or behaviors — different calculation methods, validation rules, rendering approaches, or any family of behaviors selected at runtime. Common in pricing engines, auth providers, export formats, and notification channels.

## File locations

| File | Path |
|---|---|
| Strategy interface | `src/domain/<feature>/strategies/<name>.strategy.interface.ts` |
| Concrete strategy | `src/domain/<feature>/strategies/<variant>.strategy.ts` |
| Context (consumer) | `src/domain/<feature>/<feature>.service.ts` (or wherever the strategy is used) |
| Test | `test/domain/<feature>/strategies/<variant>.strategy.test.ts` |

Adapt paths to the project's existing directory structure.

## Dependencies

- Strategy interface: domain types only
- Concrete strategies: may depend on services, configs, or external libraries depending on the variant
- Context: depends on the strategy interface, not concrete strategies

## Template

```typescript
// --- Strategy interface ---

export interface I<Name>Strategy {
  execute(input: InputType): Promise<OutputType>;
}

// --- Concrete strategy A ---

export class <VariantA>Strategy implements I<Name>Strategy {
  async execute(input: InputType): Promise<OutputType> {
    // variant A algorithm
  }
}

// --- Concrete strategy B ---

export class <VariantB>Strategy implements I<Name>Strategy {
  async execute(input: InputType): Promise<OutputType> {
    // variant B algorithm
  }
}

// --- Context (consumer) ---

export class <Feature>Service {
  constructor(
    private strategy: I<Name>Strategy,
  ) {}

  setStrategy(strategy: I<Name>Strategy): void {
    this.strategy = strategy;
  }

  async doWork(input: InputType): Promise<OutputType> {
    return this.strategy.execute(input);
  }
}
```

## Wiring

Register concrete strategies in the DI container. The context receives a strategy via injection or a factory that selects the appropriate strategy at runtime.

## Conventions

- All strategies implement the same interface — they are fully interchangeable
- Strategy selection logic lives outside the strategies (factory, config, or context)
- Each strategy is independently testable
- Prefer composition over inheritance — strategies are injected, not extended

## Tests

- Test each concrete strategy independently against the interface contract
- Test the context with different strategies to verify interchangeability
- Test strategy selection logic (factory or config-based selection)
- Each strategy should produce distinct, verifiable output for the same input
