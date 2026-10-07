# Chain of Responsibility Pattern

> **Type**: template
> **Category**: behavioral
> **Triggers**: chain of responsibility, handler chain, pipeline, middleware, pass along until handled, escalation
> **Related**: composite, command, decorator, mediator

## Intent

Avoid coupling the sender of a request to its receiver by giving more than one object a chance to handle the request. Chain the receiving objects and pass the request along the chain until an object handles it.

## When to use

Scaffold a chain when **more than one object may handle a request**, the handler is not known in advance, and the sender should not have to pick.

- More than one object may handle a request, and which one is determined at run-time.
- You want to issue a request to one of several objects without specifying the receiver explicitly.
- The set of objects that can handle a request should be **specifiable dynamically** — configured, reordered, or extended without touching the sender.
- Requests escalate: validation layers, approval tiers, fallback resolvers, middleware pipelines.

**Not when:**
- Exactly one handler is possible and known. Call it; `minimalism` forbids the machinery.
- Every link must run — that is a pipeline of `decorator.md` wrappers, not a chain that stops at the first match.
- The routing is a lookup from a key to a handler. A map is simpler, faster, and easier to debug.
- Handling must be **guaranteed**. A chain cannot promise receipt (see Consequences); use an explicit dispatcher with an exhaustiveness check.

## Participants

| Role | Responsibility | Path |
|---|---|---|
| Handler | Declares the handling interface and (optionally) the successor link | `<domain layer>/Handlers/I<Name>Handler.<ext>` (shared, create once) |
| ConcreteHandler | Handles requests it is responsible for; otherwise forwards to its successor | `<domain layer>/<feature>/Handlers/<Name>Handler.<ext>` |
| Client | Initiates the request to the first handler in the chain | `<domain layer>/<feature>/<Feature>Service.<ext>` |
| Chain builder | Assembles handler order in one place | `<domain layer>/<feature>/Handlers/<Name>ChainBuilder.<ext>` |
| Test — handler | Verifies each handler's handle/forward decision in isolation | `<test tree>/<feature>/Handlers/<Name>HandlerTests.<ext>` |
| Test — chain | Verifies ordering, short-circuit, and the unhandled case | `<test tree>/<feature>/Handlers/<Name>ChainTests.<ext>` |

Adapt paths to the project's structure (per `.omp/agent-config.md` § Layer Boundaries).

### Structure

```
  Client ──▶ HandlerA ──successor──▶ HandlerB ──successor──▶ HandlerC ──▶ (unhandled)
              │ can I handle?         │                       │
              └─ yes → handle, stop   └─ no → forward          └─ …
```

**Collaborations:** when a client issues a request, it propagates along the chain until a ConcreteHandler takes responsibility for handling it.

## Dependencies

- Handler interface: domain types only — no framework imports.
- ConcreteHandler: its successor via the Handler interface, plus whatever its own decision needs (repositories, policy services) injected via constructor.
- Client: the first handler, as the Handler interface. It must not know the chain's length or membership.

## Template

Use the active pack's `scaffold-snippets.md` for the concrete idiom. Shape:

```
// Handler (create once): I<Name>Handler with handle(request) -> result-or-unhandled,
//   and a successor reference (or take the successor as a constructor argument —
//   preferred, since it makes the chain immutable once built).
// ConcreteHandler: <Name>Handler decides canHandle(request); if yes it handles and
//   STOPS; if no it delegates to the successor. Never both.
// Chain builder: one function/class that constructs the ordered chain and returns
//   its head. Order lives here and nowhere else.
// Terminal behaviour: the last successor is an explicit terminal handler that either
//   returns a documented default or raises a domain error — never a null successor.
```

## Wiring

Register each ConcreteHandler and the chain builder in the DI container (per `.omp/agent-config.md` § Pattern Compliance); resolve the chain's **head** as the Handler binding so clients receive the assembled chain. Build the order explicitly in the builder rather than relying on registration order, which is invisible and easy to perturb. Where the chain is configurable, drive the order from configuration read at the composition root.

## Conventions

- A handler either handles the request or forwards it — never both, and never partially.
- Order is defined in exactly one place, the chain builder, and is documented there because behaviour depends on it.
- Prefer injecting the successor at construction so the chain is immutable after assembly.
- The chain always terminates in an explicit terminal handler. A null successor is how this pattern fails silently.
- Handlers do not know their position, the chain's length, or their peers.
- Handlers stay side-effect-free until they commit to handling; a handler that mutates then forwards leaves partial state behind.
- No framework imports in domain handlers. Use the project logger at the chain head, not in every link.

## Tests

- Test each ConcreteHandler in isolation with a fake successor: assert it handles what it should and forwards what it should not.
- Assert a handler that handles a request does **not** call its successor — the short-circuit is the contract.
- Test the assembled chain end to end: a request matching a late handler reaches it, having been declined by the earlier ones.
- Test the unhandled case explicitly — a request no handler accepts must hit the terminal and produce the documented default or error.
- Test order sensitivity: swap two handlers in the builder and assert the documented behaviour changes as expected.

## Consequences

1. **Reduced coupling.** Neither the sender nor the receiver knows the other explicitly, and an object in the chain need not know the chain's structure. The sender keeps a single reference to the head instead of references to every candidate receiver.
2. **Added flexibility in assigning responsibilities to objects.** You can add or change responsibilities by changing the chain at run-time — reordering, inserting, or removing handlers without touching sender or handler code.
3. **Cost: receipt is not guaranteed.** Because no receiver is named explicitly, a request can fall off the end of the chain unhandled — and if the chain is misconfigured, silently. The explicit terminal handler in the Conventions above exists precisely to convert that silence into a visible failure.
4. **Cost: harder to observe.** Following a request through a long chain is slow at debug time; log the entry and the deciding handler so traces name the link that took responsibility.
