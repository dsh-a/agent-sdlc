# Builder — Dart idiom

> **Shape**: `.claude/agents/scaffold/builder.md`
> **Source**: illustrative (no project exemplar)

**Check first:** Dart has named and optional constructor arguments, so a long parameter list is
not a reason to build a Builder. Most builder proposals in this stack are answered by:

```dart
Order({required this.id, this.notes, this.total = 0});
```

Use a real builder only for genuine multi-step assembly producing different representations —
a query compiler, a document exporter. Dart's cascade operator carries the step sequence:

```dart
abstract interface class IReportBuilder {
  void addHeader(String title);
  void addRow(ReportRow row);
  Report build();
}

class CsvReportBuilder implements IReportBuilder {
  final StringBuffer _buf = StringBuffer();
  // ... addHeader / addRow append to _buf

  @override
  Report build() {
    if (_buf.isEmpty) throw const DomainException('Report has no content.');
    final report = CsvReport(_buf.toString());
    _buf.clear(); // single-use: never leak parts into the next product
    return report;
  }
}

// Director drives the order; the builder owns the representation.
final report = (CsvReportBuilder()
      ..addHeader('Orders')
      ..addRow(row))
    .build();
```

Builders hold mutable partial state, so they are never registered as a shared instance — inject a
factory that returns a fresh one.
