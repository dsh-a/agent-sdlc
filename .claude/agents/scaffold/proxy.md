# Proxy Pattern

> **Type**: template
> **Category**: structural
> **Triggers**: proxy, surrogate, placeholder, lazy loading, access control, remote stub, smart reference
> **Aliases**: Surrogate
> **Related**: adapter, decorator, facade, flyweight

## Intent

Provide a surrogate or placeholder for another object to control access to it.

## When to use

Scaffold a proxy when a client should hold something that **behaves exactly like** the real object, but access to that object must be deferred, guarded, or performed elsewhere. Name which kind you are building:

- **Virtual proxy** — creating the real object is expensive, so create it on demand (lazy loading, large assets, deferred connections).
- **Protection proxy** — access must be checked before the real object is reached (permissions, tenancy, feature gates).
- **Remote proxy** — the real object lives in another address space, and the proxy is the local representative that handles the transport.
- **Smart reference** — extra bookkeeping is needed on access (reference counts, lock acquisition, load-on-first-use, usage metering).

**Not when:**
- You are adding behaviour rather than controlling access → `decorator.md`. The shape is identical; the *intent* differs, so state which one this is and name the class accordingly.
- You are converting an interface → `adapter.md`.
- You are simplifying a subsystem → `facade.md`.
- The real object is cheap and unguarded. The indirection buys nothing and `minimalism` forbids it.

## Participants

| Role | Responsibility | Path |
|---|---|---|
| Subject | The interface shared by RealSubject and Proxy, so the proxy is substitutable | `<domain layer>/<feature>/I<Name>.<ext>` |
| RealSubject | The real object the proxy represents | `<domain layer>/<feature>/<Name>.<ext>` or `<data layer>/…` |
| Proxy | Maintains a reference to the RealSubject, controls access, and may create or delete it | `<data layer>/<feature>/Proxies/<Kind><Name>Proxy.<ext>` |
| Client | Works against the Subject interface, unaware whether it holds a proxy | `<domain layer>/<feature>/<Feature>Service.<ext>` |
| Test | Verifies access control, deferral, and pass-through against a fake RealSubject | `<test tree>/<feature>/Proxies/<Kind><Name>ProxyTests.<ext>` |

Adapt paths to the project's structure (per `.omp/agent-config.md` § Layer Boundaries).

### Structure

```
  Client ──▶ «interface» Subject
                     △
        ┌────────────┴────────────┐
   RealSubject ◀────realSubject─── Proxy
   + request()                  + request()
                                  → check/create, then realSubject.request()
```

**Collaborations:** the Proxy forwards requests to the RealSubject when appropriate, depending on the kind of proxy. A virtual proxy may instantiate the RealSubject on first use; a protection proxy may refuse the request entirely.

## Dependencies

- Subject interface and RealSubject: domain types only — no framework imports.
- Proxy: the Subject interface, plus whatever its control concern needs — an authorisation service, a transport client, a lock, a factory for lazy creation.
- Client: the Subject interface only.

## Template

Use the active pack's `scaffold-snippets.md` for the concrete idiom. Shape:

```
// Subject: I<Name> — identical surface for the real object and the proxy.
// RealSubject: <Name> — the actual behaviour, unaware it is proxied.
// Proxy: <Kind><Name>Proxy implements I<Name> and holds either the RealSubject or a
//   factory that creates it.
//     virtual    -> create on first use, then cache; guard against double creation.
//     protection -> check the caller's rights first; deny with a domain error.
//     remote     -> serialise the call, invoke transport, deserialise, map errors.
//     smart ref  -> take/release the resource around the forwarded call.
//   The kind belongs in the class name so intent is readable at the wiring site.
```

## Wiring

Bind the Subject interface to the Proxy in the DI container (per `.omp/agent-config.md` § Pattern Compliance), injecting the RealSubject — or a factory for it, when creation must stay deferred — into the proxy. Injecting an already-constructed RealSubject into a **virtual** proxy defeats it entirely; inject the factory. Clients resolve the Subject interface and are unaffected either way.

## Conventions

- The proxy implements the Subject interface exactly. Extra public methods leak the proxy's existence and break substitutability.
- One control concern per proxy; name the class for its kind (`LazyImageProxy`, `TenantScopedRepositoryProxy`).
- A protection proxy denies with a **domain error**, never by returning null or empty — a silent denial becomes a data bug far from the cause.
- A virtual proxy creates the RealSubject at most once, even under concurrent first access.
- The proxy holds no business rules; it controls access and forwards.
- Errors from the RealSubject pass through untouched unless the proxy's concern is explicitly to translate them (remote proxies always translate).
- Framework, transport, and SDK imports belong in the proxy, never in the Subject interface.

## Tests

- Test pass-through: arguments and results survive the proxy unchanged.
- **Virtual** — assert the RealSubject is not created until the first call, is created exactly once across repeated calls, and is created only once under concurrent access.
- **Protection** — assert an authorised caller reaches the RealSubject and an unauthorised caller does **not**, failing with a domain error; assert the RealSubject was never invoked in the denial case.
- **Remote** — test request serialisation, response mapping, and transport-failure translation.
- **Smart reference** — assert the resource is released even when the forwarded call throws.
- Test the client against a fake Subject, so it never depends on proxy specifics.

## Consequences

1. **Introduces a level of indirection when accessing an object,** and that indirection has different uses depending on the kind: a remote proxy hides that the object lives in another address space; a virtual proxy performs optimisations such as creating an object on demand; protection proxies and smart references allow housekeeping tasks at the moment of access.
2. **Lazy creation can pay for itself many times over.** Virtual proxies let a system present a complete structure while materialising only the parts actually touched.
3. **Copy-on-write becomes possible.** A proxy that counts references can defer an expensive copy until a client actually mutates the object — the deferral being the same mechanism as lazy creation.
4. **Cost: the object is no longer where you think it is.** Debugging crosses a hop, identity is no longer the RealSubject's, and a proxy that hides errors or denials quietly makes failures surface far from their cause.
