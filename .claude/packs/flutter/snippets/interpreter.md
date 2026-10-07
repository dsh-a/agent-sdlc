# Interpreter — Dart idiom

> **Shape**: `.claude/agents/scaffold/interpreter.md`
> **Source**: illustrative (no project exemplar)

A `sealed` expression hierarchy plus a `switch` expression gives exhaustive evaluation — add a
node type and every `switch` fails to compile until it is handled:

```dart
sealed class FilterExpr {
  const FilterExpr();
}

class TagIs extends FilterExpr {
  final String tag;
  const TagIs(this.tag);
}

class AndExpr extends FilterExpr {
  final FilterExpr left, right;
  const AndExpr(this.left, this.right);
}

class NotExpr extends FilterExpr {
  final FilterExpr inner;
  const NotExpr(this.inner);
}

bool evaluate(FilterExpr expr, FilterContext ctx) => switch (expr) {
  TagIs(:final tag) => ctx.tags.contains(tag),
  AndExpr(:final left, :final right) =>
    evaluate(left, ctx) && evaluate(right, ctx),
  NotExpr(:final inner) => !evaluate(inner, ctx),
};
```

- Expression nodes are immutable and side-effect-free; all evaluation state lives in the context,
  so one tree can be evaluated against many contexts.
- The parser owns validation. By the time a tree exists it is well-formed, so nodes need no
  defensive checks.
- Parse once and reuse the tree — re-parsing per evaluation is the usual performance mistake.
- Bound recursion depth when input is untrusted.
- Adding a new *operation* over the tree (pretty-print, optimise) is a `visitor` job — or, in
  Dart, simply another top-level `switch` function like the one above.
