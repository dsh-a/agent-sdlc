# Facade

> **Type**: template

## When to use

Scaffold a facade when the task requires a simplified interface over multiple subsystems — aggregating several repositories, services, or use cases into a cohesive API for a feature area. Facades reduce coupling between consumers and complex internal structures.

## File locations

| File | Path |
|---|---|
| Facade | `src/domain/<feature>/<feature>.facade.ts` |
| Test | `test/domain/<feature>/<feature>.facade.test.ts` |

Adapt paths to the project's existing directory structure.

## Dependencies

- Repository interfaces
- Service interfaces
- Other facades or use cases
- Injected via constructor

## Template

```typescript
export class <Feature>Facade {
  constructor(
    private readonly someRepository: ISomeRepository,
    private readonly otherRepository: IOtherRepository,
    private readonly someService: ISomeService,
  ) {}

  // Public methods that orchestrate across multiple subsystems
  async getFeatureOverview(id: string): Promise<FeatureOverview> {
    const [primary, related] = await Promise.all([
      this.someRepository.findById(id),
      this.otherRepository.findByParentId(id),
    ]);
    return { primary, related };
  }
}
```

## Wiring

Register in the DI container. Consumers depend on the facade, not on the individual repositories/services it wraps.

## Conventions

- Dependencies are interfaces, not implementations
- Contains cross-subsystem orchestration, not business rules (those go in use cases)
- Methods should represent meaningful feature-level operations, not thin wrappers
- No framework imports — domain layer is pure TypeScript

## Tests

- Mock all dependencies at the interface level
- Test orchestration logic (correct calls made, results combined properly)
- Test error propagation (one dependency fails → facade handles it appropriately)
