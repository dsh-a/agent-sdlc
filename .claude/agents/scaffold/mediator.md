# Mediator Pattern

> **Type**: template
> **Category**: behavioral
> **Triggers**: mediator, coordinator, decouple many-to-many, central coordination, colleague objects
> **Related**: facade, observer, chain-of-responsibility

## Intent

Define an object that encapsulates how a set of objects interact. Mediator promotes loose coupling by keeping objects from referring to one another explicitly, and it lets you vary their interaction independently.

## When to use

Scaffold a mediator when a **set of peers all need to react to one another**, and wiring them directly has produced a web of references that no single object explains.

- A set of objects communicate in well-defined but **complex** ways, and the resulting interdependencies are unstructured and hard to follow.
- Reusing an object is difficult because it refers to and communicates with many others.
- A behaviour distributed between several classes should be **customisable without a lot of subclassing** — the interaction is the thing that varies.
- Typical fits: a form whose fields enable and validate each other, a toolbar whose controls constrain one another, a workflow coordinating several services.

**Not when:**
- Communication is one-way from a source to indifferent listeners → `observer.md`. A mediator coordinates peers; an observer broadcasts.
- You want a simpler entry point into a subsystem that does not talk back → `facade.md`. A facade is one-directional; a mediator is bidirectional.
- Only two objects interact. Let them; `minimalism` forbids a coordinator for a pair.
- The interaction is a linear pass-along until something handles it → `chain-of-responsibility.md`.

## Participants

| Role | Responsibility | Path |
|---|---|---|
| Mediator | Declares the interface colleagues use to communicate | `<domain layer>/<feature>/I<Name>Mediator.<ext>` |
| ConcreteMediator | Knows and maintains the colleagues; implements cooperative behaviour by coordinating them | `<domain layer>/<feature>/<Name>Mediator.<ext>` |
| Colleague | Knows only its mediator; notifies it instead of its peers | `<domain layer>/<feature>/Colleagues/<Name>Colleague.<ext>` |
| Test — mediator | Verifies coordination rules against fake colleagues | `<test tree>/<feature>/<Name>MediatorTests.<ext>` |
| Test — colleague | Verifies each colleague notifies the mediator and holds no peer references | `<test tree>/<feature>/Colleagues/<Name>ColleagueTests.<ext>` |

Adapt paths to the project's structure (per `.omp/agent-config.md` § Layer Boundaries).

### Structure

```
   without mediator            with mediator
   A ──▶ B ──▶ C                A   B   C   D
   ▲  ╲  │  ╱  │                 ╲  │  │  ╱
   │   ╳ ▼ ╳   ▼                  ▼ ▼  ▼ ▼
   D ◀── ─── ──┘                 ConcreteMediator
   (n² couplings)              (n couplings, one place to read)
```

**Collaborations:** colleagues send and receive requests from a Mediator object. The mediator implements the cooperative behaviour by routing requests between the appropriate colleagues; no colleague ever names another.

## Dependencies

- Mediator interface and colleagues: domain types only — no framework imports.
- ConcreteMediator: the colleagues it coordinates, plus any services the coordination rules need.
- Colleague: its mediator, via the Mediator interface. Nothing else about the group.

## Template

Use the active pack's `scaffold-snippets.md` for the concrete idiom. Shape:

```
// Mediator: I<Name>Mediator with notify(sender, event) — or one named method per
//   interaction (preferred: named methods read far better than a stringly event).
// ConcreteMediator: <Name>Mediator holds references to its colleagues and implements
//   every coordination rule. This is the ONLY place the group's rules live.
// Colleague: <Name>Colleague holds I<Name>Mediator and calls it when its own state
//   changes. It holds NO reference to any peer and knows nothing of the group.
// Registration: colleagues are attached to the mediator at construction.
```

## Wiring

Register the ConcreteMediator in the DI container (per `.omp/agent-config.md` § Pattern Compliance) and construct the colleague set with it at the composition root, so the group is assembled in one visible place. Colleagues receive the Mediator interface by constructor injection. Avoid making the mediator a global accessor — its whole value is that the interaction is explicit and reviewable at one wiring site.

## Conventions

- Colleagues never reference each other. A direct peer call is the pattern being abandoned.
- Prefer named interaction methods on the mediator over a generic `notify(event)`; the mediator's interface should read as the group's protocol.
- The mediator owns the interaction rules; colleagues own their own state and behaviour. A mediator reaching into a colleague's internals has taken over its job.
- Guard against notification loops: a mediator that updates a colleague which notifies back must not re-enter. Suppress re-entrancy explicitly.
- Keep the mediator to one cohesive group. When it coordinates two unrelated sets of colleagues, split it — this is how the god-object failure begins.
- No framework imports in the domain layer.

## Tests

- Test the mediator against fake colleagues: assert that one colleague's notification produces the correct calls on the others.
- Test each colleague in isolation with a fake mediator: assert it notifies on state change and never touches a peer.
- Test re-entrancy explicitly — a colleague notifying during a mediator-driven update must not loop.
- Test the assembled group for one representative end-to-end interaction.
- Assert colleague classes carry no field or import naming another colleague; that is the pattern's structural invariant.

## Consequences

1. **Limits subclassing.** A mediator localises behaviour that would otherwise be distributed among several objects, so changing that behaviour means subclassing the Mediator alone — colleagues can be reused as they are.
2. **Decouples colleagues.** You can vary and reuse colleague classes independently, because none of them knows the others exist.
3. **Simplifies object protocols.** It replaces many-to-many interactions with one-to-many between the mediator and its colleagues — far easier to understand, maintain, and extend.
4. **Abstracts how objects cooperate.** Making mediation an independent concept lets you focus on how objects interact apart from their individual behaviour, which clarifies what is really going on in a system.
5. **Cost: it centralises control.** The mediator trades interaction complexity for mediator complexity — it can become a monolith that is harder to maintain than the tangle it replaced. Keeping one mediator per cohesive group is the discipline that prevents this.
