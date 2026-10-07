# State — Dart idiom

> **Shape**: `.claude/agents/scaffold/state.md`
> **Source**: illustrative (no project exemplar)

> Not to be confused with Flutter's `State<T>` widget class, which is unrelated to this pattern.

A `sealed` state hierarchy plus exhaustive `switch` makes illegal transitions a compile-time
concern rather than a run-time one:

```dart
sealed class OrderState {
  const OrderState();
}

class Draft extends OrderState { const Draft(); }
class Submitted extends OrderState {
  final DateTime at;
  const Submitted(this.at);
}
class Approved extends OrderState { const Approved(); }

class Order {
  OrderState state = const Draft();

  void submit() {
    state = switch (state) {
      Draft() => Submitted(DateTime.now()),
      Submitted() => throw const DomainException('Order already submitted.'),
      Approved() => throw const DomainException('Approved orders cannot be resubmitted.'),
    };
  }
}
```

- An operation illegal in the current state fails with a domain error **naming the state**; a
  silent no-op turns an invalid transition into a data bug.
- Adding a state breaks every `switch` at compile time — that is the safety property; never add a
  `default:` clause, which discards it.
- Stateless states are `const` and therefore shared for free (see `flyweight`).
- Persisted status values map to exactly one state, exhaustively; an unknown stored value must
  fail loudly on load.
- Document the state diagram beside the classes — the classes *are* the machine.
