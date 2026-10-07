# Template Method Pattern

> **Type**: template
> **Category**: behavioral
> **Triggers**: template method, algorithm skeleton, hook method, defer steps to subclass, invariant steps, Hollywood principle
> **Related**: strategy, factory-method

## Intent

Define the skeleton of an algorithm in an operation, deferring some steps to subclasses. Template Method lets subclasses redefine certain steps of an algorithm without changing the algorithm's structure.

## When to use

Scaffold a template method when several variants share the **same sequence of steps** and differ only in what some of those steps do — and the sequence itself must not vary.

- To implement the invariant parts of an algorithm once, and leave it to subclasses to implement the behaviour that can vary.
- When common behaviour among subclasses should be factored and localised in a common class to **avoid duplication** — the classic "refactor to generalise": identify the differences in existing code and separate them into new operations.
- To **control subclass extensions**: define a template method that calls hook operations at specific points, permitting extension only at those points.

**Not when:**
- The whole algorithm varies, not just its steps → `strategy.md`. Prefer strategy when composition is available: it swaps at run-time, avoids inheritance, and lets one object use several algorithms.
- The language discourages or forbids the required inheritance, or the base class already has another reason to be subclassed.
- There is one implementation. `minimalism` forbids an abstract base for a single case.
- Subclasses would need to change the **order** of steps. That is not this pattern; the fixed order is the entire contract.

## Participants

| Role | Responsibility | Path |
|---|---|---|
| AbstractClass | Defines the template method holding the algorithm's skeleton; declares the primitive operations | `<domain layer>/<feature>/<Name>Base.<ext>` |
| ConcreteClass | Implements the primitive operations for one variant | `<domain layer>/<feature>/<Variant><Name>.<ext>` |
| Test — variant | Verifies each concrete variant's steps and its end-to-end result | `<test tree>/<feature>/<Variant><Name>Tests.<ext>` |
| Test — skeleton | Verifies the step order via a probe subclass | `<test tree>/<feature>/<Name>BaseTests.<ext>` |

Adapt paths to the project's structure (per `.omp/agent-config.md` § Layer Boundaries).

### Structure

```
  AbstractClass
  + templateMethod()        ← final; owns the ORDER
      step1()               ← abstract: subclass must implement
      hook()                ← virtual with a default: subclass may override
      step2()               ← abstract
          △
  ┌───────┴───────┐
 VariantA      VariantB     ← implement steps only; never the order
```

**Collaborations:** ConcreteClass relies on AbstractClass to implement the invariant steps of the algorithm. Control flows from the base class down to the subclass — the subclass never calls the template method's steps itself.

## Dependencies

- AbstractClass: domain types only — no framework imports. It owns the sequence and nothing environment-specific.
- ConcreteClass: whatever its own steps need, injected via constructor.
- Callers depend on the AbstractClass type, never on a concrete variant.

## Template

Use the active pack's `scaffold-snippets.md` for the concrete idiom. Shape:

```
// AbstractClass: <Name>Base with a single public template method that calls the steps
//   in a fixed order. Seal/finalise it where the language allows — an overridable
//   template method destroys the guarantee the pattern exists to give.
//   Declare REQUIRED steps abstract (a missing one is then a compile error) and
//   OPTIONAL hooks as virtual with a do-nothing or sensible default.
//   Name steps for their role so the skeleton reads as documentation.
// ConcreteClass: <Variant><Name> overrides the steps; NEVER the template method,
//   and never calls another step directly.
```

## Wiring

Register each ConcreteClass against the AbstractClass type in the DI container (per `.omp/agent-config.md` § Pattern Compliance), selecting the variant at the composition root. Consumers depend on the base type. Where the variant is chosen per request, inject a factory rather than resolving inside the template method — the skeleton must stay free of selection logic.

## Conventions

- The template method is **final/sealed**. If a subclass can override the order, there is no skeleton.
- Minimise the number of primitive operations a subclass must override; every required step is a burden on every variant. Prefer more hooks with defaults over more abstract methods.
- Name the steps for their role in the algorithm, and name hooks so their optionality is obvious (`onBeforeX`, `shouldY`).
- Document which operations **must** be overridden and which **may** be — the base class is the contract, and an undocumented one is guessed at.
- Steps do not call one another; only the template method sequences them. Step-to-step calls reintroduce the order into the subclass.
- Hooks have safe no-op defaults, so a variant ignoring them behaves correctly.
- Keep the inheritance one level deep. A hierarchy of template methods is the fragile-base-class problem arriving.
- No framework imports in the base class.

## Tests

- Test each ConcreteClass end to end through the template method — that is the public surface.
- Test the skeleton with a probe subclass that records step invocations, and assert the exact **order**. This is the only test of the pattern's actual contract.
- Test hook defaults: a variant overriding nothing optional still behaves correctly.
- Test that a step throwing aborts the sequence as documented and does not leave partial state.
- Assert (by review or by test) that no ConcreteClass overrides the template method.
- Test the shared steps once in the base tests rather than repeating them per variant.

## Consequences

1. **A fundamental technique for code reuse.** Template methods are especially important in class libraries: they are the means by which a library factors out common behaviour and lets applications supply the rest.
2. **Inverted control — the "Hollywood principle": don't call us, we'll call you.** The parent class calls the operations of a subclass, never the other way around. This is what lets a framework own the flow while applications own the steps.
3. **Explicit extension points.** Because hooks are declared, the base class states exactly where subclasses may intervene — extension becomes reviewable rather than arbitrary.
4. **Cost: inheritance, with everything that brings.** Variants are bound at compile time, a class can have only one template-method parent, and changes to the base ripple to every subclass. Where these bite, `strategy.md` achieves the same variation through composition.
5. **Cost: the skeleton can accumulate hooks.** Each new variant tempts you to add another hook, and a base class with a dozen extension points is no longer a readable algorithm. That growth is the signal to move to composition.
