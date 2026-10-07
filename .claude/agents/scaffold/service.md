# Service

> **Type**: template
> **Category**: architecture
> **Triggers**: service, infrastructure wrapper, external API client, platform feature, email storage cache auth
> **Related**: interface, adapter, facade, proxy

## Intent

Wrap an infrastructure concern behind a domain-facing contract, so that application code can use an external capability without depending on it.

## When to use

Scaffold a service when the task involves wrapping an infrastructure concern — external APIs, platform features, email, file storage, caching, auth providers, etc. Services live at the infrastructure/data layer.

- Domain or application code needs a capability that lives outside the process: a network call, the file system, a platform API, a third-party SDK.
- The external dependency must be substitutable in tests, and its failures must be translated into terms the domain understands.
- The capability is used from more than one place, or its setup is non-trivial enough that repeating it invites divergence.

**Not when:**
- The logic is a business operation with rules and validation → `use-case.md`. A service provides a capability; a use case decides what to do with it.
- You are aggregating several existing services into a feature-level API → `facade.md`.
- The work is purely conforming a third-party interface to yours, with no additional concern → that is `adapter.md`, and naming it accurately helps reviewers.

## Participants

| Role | Responsibility | Path |
|---|---|---|
| Service interface | The domain-facing contract, in domain vocabulary and domain types | `<data layer>/<feature>/Services/I<Name>Service.<ext>` |
| Service implementation | Calls the external system and translates its data and its failures | `<data layer>/<feature>/Services/<Name>Service.<ext>` |
| External client / SDK | The third-party capability being wrapped (injected, never constructed inline) | external dependency |
| Consumer | Depends on the service interface | `<domain layer>/<feature>/<Feature>Service.<ext>` |
| Test | Verifies success paths, error translation, and edge cases against a mocked client | `<test tree>/<feature>/Services/<Name>ServiceTests.<ext>` |

Adapt paths to the project's structure (per `.omp/agent-config.md` § Layer Boundaries).

### Structure

```
  domain layer     Consumer ──▶ «interface» INameService
  ──────────────────────────────────────  │  ── layer boundary
  data layer                        NameService ──▶ ExternalClient / SDK
                                    (translates data AND errors)
```

**Collaborations:** the consumer calls the interface; the implementation calls the external client, maps its response to domain types, and converts its failures into domain errors.

## Dependencies

- External SDKs or clients (injected, not imported directly in domain)
- Configuration/environment values
- Logger

## Template

Use the active pack's `scaffold-snippets.md` for the concrete idiom. Shape:

```
// Interface: I<Name>Service — the public contract in DOMAIN terms. No SDK types
//   in parameters, returns, or errors.
// Implementation: <Name>Service implements I<Name>Service.
//   - external client, config, and logger injected via constructor
//   - each method: map domain args -> client args, call, map response -> domain type
//   - wrap the call: catch external failures, log with context, and rethrow a
//     domain-meaningful error carrying the original as its cause
//   - no retry/caching logic here unless it IS the service's concern (see decorator.md)
```

## Wiring

Register the interface-implementation binding in the DI container. Domain/application code depends on the interface, not the implementation. The external client and its configuration are constructed at the composition root and injected in; a service that reaches for global config or constructs its own client cannot be tested or reconfigured.

## Conventions

- Always define an interface — services are infrastructure, and domain code must not depend on implementations.
- Constructor takes external dependencies via injection.
- Wrap external calls with error handling — translate external errors to domain-meaningful errors, preserving the original as a cause.
- No SDK or transport type appears in the interface. A leaked type puts the vendor in your domain.
- Use the project's logger, never `console.log`, and log with enough context to identify the failing call.
- The service holds no business rules; it provides a capability.
- Cross-cutting concerns (retry, caching, metrics) belong in decorators around the service, not inside it — unless that concern is the service's whole purpose.
- May use framework imports (unlike domain layer).

## Tests

- Mock external clients/SDKs.
- Test success paths with expected responses.
- Test error handling (external failure → service error translation), asserting the cause is preserved.
- Test edge cases (timeouts, empty responses, malformed data).
- Test that configuration is honoured rather than hard-coded.
- Do not test the SDK itself; test the translation on both sides of it.

## Consequences

1. **The domain stays free of infrastructure.** Application code expresses what it needs, and the vendor, transport, and platform stay on the far side of one interface.
2. **Failures become domain-shaped at a single point.** External errors are translated once, in the place that understands them, rather than leaking into every caller's error handling.
3. **Substitutable in tests and across platforms.** A fake service makes consumer tests fast and deterministic; a second implementation covers a new platform or vendor.
4. **Cost: a mapping surface that must be maintained.** Every external concept has to be translated, and an unmapped field, enum value, or failure mode fails at run-time. The translation is the service's real work, and its tests are the ones that matter.
