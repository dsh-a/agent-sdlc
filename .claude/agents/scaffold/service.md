# Service

> **Type**: template

## When to use

Scaffold a service when the task involves wrapping an infrastructure concern — external APIs, platform features, email, file storage, caching, auth providers, etc. Services live at the infrastructure/data layer.

## File locations

| File | Path |
|---|---|
| Interface | `src/infrastructure/services/<name>.service.interface.ts` |
| Implementation | `src/infrastructure/services/<name>.service.ts` |
| Test | `test/infrastructure/services/<name>.service.test.ts` |

Adapt paths to the project's existing directory structure.

## Dependencies

- External SDKs or clients (injected, not imported directly in domain)
- Configuration/environment values
- Logger

## Template

```typescript
export interface I<Name>Service {
  // public contract
}

export class <Name>Service implements I<Name>Service {
  constructor(
    private readonly client: ExternalClient,
    private readonly logger: Logger,
  ) {}

  async someOperation(params: Params): Promise<Result> {
    try {
      // call external system
    } catch (error) {
      this.logger.error('<Name>Service.someOperation failed', { error });
      throw new ServiceError('Operation failed', { cause: error });
    }
  }
}
```

## Wiring

Register the interface-implementation binding in the DI container. Domain/application code depends on the interface, not the implementation.

## Conventions

- Always define an interface — services are infrastructure, and domain code must not depend on implementations
- Constructor takes external dependencies via injection
- Wrap external calls with error handling — translate external errors to domain-meaningful errors
- Use the project's logger, never `console.log`
- May use framework imports (unlike domain layer)

## Tests

- Mock external clients/SDKs
- Test success paths with expected responses
- Test error handling (external failure → service error translation)
- Test edge cases (timeouts, empty responses, malformed data)
