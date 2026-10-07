# Flutter test-reference patterns (pack: flutter)

Read by `.claude/skills/cycle/symbol-refs.py` to say which test a matching line
sits inside. Stack-specific by construction — the script knows how to walk a
tree and track scope by indentation; it knows nothing about Dart.

| Field | Pattern |
|---|---|
| test_decl | `^\s*(?:await\s+)?test(?:Widgets)?(?:WithLeaks)?\(\s*(?P<q>['"])(?P<name>.*?)(?P=q)` |
| group_decl | `^\s*group\(\s*(?P<q>['"])(?P<name>.*?)(?P=q)` |

Matched against the shapes a Dart test file uses:

```dart
group('FooRepository', () {
  test('inserts row', () async {
    ...
  });

  testWidgets('renders a spinner while loading', (tester) async {
    ...
  });
});
```

A hit inside the first is reported as `FooRepository > inserts row`.

## Rules for editing this table

- **`name` is the contract.** A pattern without a `name` group is ignored — the
  script will not fall back to the matched text, because a name it composed is a
  row the test agent then tries to find and cannot.
- **No `|` anywhere in a pattern.** The cell is a markdown table cell and a pipe
  ends it. Use a non-capturing optional group rather than alternation; both
  patterns here are written that way for this reason. `test(?:Widgets)?` is the
  alternation `test|testWidgets` rewritten to obey the rule.
- **Anchor to the start of the line.** Scope is tracked by the indentation of
  the matching line, so a `test(` that appears mid-line — inside a string, a
  comment, or a chained call — would register at the wrong depth. `^\s*` is what
  keeps that out.
- **Backreferenced quotes.** `(?P<q>['"])...(?P=q)` matches `'name'` and
  `"name"` without letting an apostrophe inside a double-quoted name end the
  match early. Dart style is single quotes; tests written by hand are not
  always.
- **A pattern that does not compile is skipped with a warning**, not fatal. A
  broken row costs you the Test name column; the file and line stay exact.

If a project wraps its tests in a custom helper this table does not match, the
script reports `names=partial` and leaves those cells `—` rather than guessing.
That is the signal to add a row here.
