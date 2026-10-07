# Chain of Responsibility — Dart idiom

> **Shape**: `.claude/agents/scaffold/chain-of-responsibility.md`
> **Source**: illustrative (no project exemplar)

Take the successor as a constructor argument so the chain is immutable once built:

```dart
abstract interface class IValidationHandler {
  /// Returns null when handled; otherwise the request continues down the chain.
  ValidationError? handle(OrderDraft draft);
}

class QuantityHandler implements IValidationHandler {
  final IValidationHandler _next;
  const QuantityHandler(this._next);

  @override
  ValidationError? handle(OrderDraft draft) {
    if (draft.items.any((i) => i.quantity <= 0)) {
      return const ValidationError('Quantity must be positive.');  // handled, stop
    }
    return _next.handle(draft);                                     // not mine, forward
  }
}

/// Explicit terminal — never a null successor.
class TerminalHandler implements IValidationHandler {
  const TerminalHandler();
  @override
  ValidationError? handle(OrderDraft draft) => null; // documented default
}

// Order lives in one place.
IValidationHandler buildChain() =>
    QuantityHandler(StockHandler(const TerminalHandler()));
```

- A handler either handles or forwards — never both, never partially.
- The chain always terminates in an explicit terminal handler. A null successor is how this
  pattern fails silently.
- Handlers stay side-effect-free until they commit to handling.
- If every link must run, this is a `decorator` pipeline, not a chain.
