# Strategy Pattern

> **Type**: template
> **Category**: behavioral
> **Triggers**: strategy, policy, interchangeable algorithm, swap behaviour, pluggable rule, export format, pricing engine
> **Aliases**: Policy
> **Related**: state, template-method, decorator, flyweight, bridge

## Intent

Define a family of algorithms, encapsulate each one, and make them interchangeable. Strategy lets the algorithm vary independently from clients that use it.

## When to use

Scaffold a strategy when the task requires **interchangeable algorithms or behaviours** — different calculation methods, validation rules, sync strategies, or any family of behaviours selected at run-time. Common for export formats, notification channels, pricing engines, or auth providers.

- Many related classes differ only in their behaviour. Strategies configure one class with one of many behaviours.
- You need **different variants of an algorithm** — for example, trading space against time.
- An algorithm uses data that clients should not know about; a strategy hides complex, algorithm-specific structures.
- A class defines many behaviours that appear as **multiple conditional branches** in its operations. Move each branch into its own strategy class.

**Not when:**
- The object moves through a lifecycle and its behaviour follows its own state → `state.md`. Strategies are handed in and do not change themselves; states transition themselves and know their successors.
- Only the *steps* of a fixed algorithm vary, and the skeleton is shared → `template-method.md`.
- You are layering behaviour around a call rather than replacing it → `decorator.md`.
- There is one algorithm. `minimalism` forbids an abstraction with a single implementation.

## Participants

| Role | Responsibility | Path |
|---|---|---|
| Strategy | Declares the interface common to all supported algorithms | `<domain layer>/<feature>/Strategies/I<Name>Strategy.<ext>` |
| ConcreteStrategy | Implements one algorithm behind the Strategy interface | `<domain layer>/<feature>/Strategies/<Variant><Name>Strategy.<ext>` |
| Context (consumer) | Configured with a strategy; delegates the work to it | `<domain layer>/<feature>/<Feature>Service.<ext>` |
| Selector / factory | Chooses the strategy at run-time from config or input | `<domain layer>/<feature>/Strategies/<Name>StrategyFactory.<ext>` |
| Test — strategy | Verifies each algorithm independently | `<test tree>/<feature>/Strategies/<Variant><Name>StrategyTests.<ext>` |
| Test — selection | Verifies the factory maps each key to the right strategy | `<test tree>/<feature>/Strategies/<Name>StrategyFactoryTests.<ext>` |

Adapt paths to the project's structure (per `.omp/agent-config.md` § Layer Boundaries).

### Structure

```
  Context ──strategy──▶ «interface» Strategy
  + operation()              + execute(input)
    → strategy.execute()            △
                       ┌────────────┼────────────┐
                 StrategyA      StrategyB     StrategyC
```

**Collaborations:** a context forwards requests from its clients to its strategy. Clients usually create and pass a ConcreteStrategy to the context, then interact with the context alone; the context and the strategy interact only through the Strategy interface.

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
// Selector (when chosen at run-time): maps a key/config value to a strategy in ONE
//   table, and fails with a domain error on an unknown key.
```

## Wiring

Register concrete strategies in the DI container (per `.omp/agent-config.md` § Pattern Compliance). The context receives a strategy via constructor injection or a factory that selects the appropriate strategy at run-time (e.g. based on configuration). Where strategies are stateless, register each as a single shared instance. Keep the key-to-strategy mapping in one place and fail loudly at startup if a configured key has no registered strategy.

## Conventions

- All strategies implement the same abstraction — they are fully interchangeable.
- Strategy selection logic lives outside the strategies (factory, config, or context). A strategy that decides whether it applies has become a `chain-of-responsibility.md` link.
- Concrete strategies are stateless where possible.
- Each strategy is independently testable in isolation.
- The Strategy interface is the same for every variant, even when a particular variant ignores some of its input — that is the price of interchangeability, and it should stay small enough not to hurt.
- No framework imports in domain strategies.
- Use the project logger in the context/consumer, not in individual strategies unless complex.

## Tests

- Test each concrete strategy independently.
- Test the context with different strategies to verify interchangeability.
- Test strategy selection logic (factory or config-based selection), including the unknown-key failure.
- Each strategy should produce distinct, verifiable output for the same input — if two produce identical results for every input, one of them is redundant.
- Test the context against a fake strategy to prove it holds no algorithm-specific logic.

## Consequences

1. **Families of related algorithms.** A hierarchy of strategies factors out common functionality, so the algorithms can be reused and compared on equal terms.
2. **An alternative to subclassing.** Subclassing the context to vary behaviour hard-wires the algorithm into the context and makes it harder to change independently. Encapsulating the algorithm in a strategy lets you vary it separately and swap it at run-time.
3. **Eliminates conditional statements.** Strategy replaces the switch or `if`-chain that selects behaviour; when different behaviours are lumped into one class, conditionals are hard to avoid — separate classes remove them.
4. **A choice of implementations.** The same interface can expose implementations with different space/time trade-offs, chosen per deployment or per request.
5. **Cost: clients must be aware of different strategies.** A client has to understand how strategies differ in order to select one, which exposes implementation concerns it might otherwise be spared.
6. **Cost: communication overhead between strategy and context.** The interface is shared by all strategies, so some will not use all the parameters passed to them — and a context that passes everything just in case couples them anyway.
7. **Cost: an increased number of objects.** Strategies multiply the object count; making them stateless and shared reduces the cost (see `flyweight.md`).
