# Factory Method — Dart idiom

> **Shape**: `.claude/agents/scaffold/factory-method.md`
> **Source**: illustrative (no project exemplar)

> **Dart's `factory` constructor is not this pattern.** A `factory` constructor returns an
> instance of its own class (often cached or a subtype) — it does not let a *subclass* decide the
> product type. Do not scaffold one and call it a factory method.

```dart
abstract class ReportCreator {
  /// The single point of instantiation — subclasses decide the concrete product.
  IReport createReport(ReportData data);

  /// Template operation, written entirely against the interface.
  Future<void> publish(ReportData data) async {
    final report = createReport(data);
    await report.render();
  }
}

class CsvReportCreator extends ReportCreator {
  @override
  IReport createReport(ReportData data) => CsvReport(data);
}
```

- The factory method returns the interface, never a concrete type.
- Leave it abstract so a missing override is a compile error; add a default only when a sensible
  default product exists.
- Where subclassing the creator is the only reason a hierarchy exists, prefer a parameterised
  factory — a single class mapping a key to a constructor, with the map in one place and an
  unknown key raising a domain error.
