# .NET test-reference patterns (pack: dotnet)

Read by `.claude/skills/cycle/symbol-refs.py` to say which test a matching line
sits inside. Stack-specific by construction — the script knows how to walk a
tree and track scope by indentation; it knows nothing about C#.

| Field | Pattern |
|---|---|
| test_decl | `^\s*(?:public\s+)?(?:async\s+)?(?:Task\s+)?(?:void\s+)?(?P<name>[A-Z]\w*)\s*\([^)]*\)\s*$` |
| group_decl | `^\s*(?:public\s+)?(?:sealed\s+)?(?:partial\s+)?(?:static\s+)?class\s+(?P<name>\w+)` |

Matched against the shapes an xUnit / NUnit file uses:

```csharp
public sealed class FooRepositoryTests
{
    [Fact]
    public async Task InsertsRow()
    {
        ...
    }
}
```

A hit inside the method is reported as `FooRepositoryTests > InsertsRow`.

## Rules for editing this table

- **`name` is the contract.** A pattern without a `name` group is ignored — the
  script will not fall back to the matched text, because a name it composed is a
  row the test agent then tries to find and cannot.
- **No `|` anywhere in a pattern.** The cell is a markdown table cell and a pipe
  ends it. Use non-capturing optional groups rather than alternation; the long
  chain of `(?:...)?` prefixes above is that rule applied to C#'s modifier
  soup.
- **The attribute is not matched; the method is.** `[Fact]` and `[Theory]` sit
  on their own line above the declaration, and the script tracks scope by the
  indentation of the *matching* line — anchoring to the attribute would give the
  method body the wrong parent. The cost is that this matches non-test methods
  in a test class too, which is harmless: they contain no symbol hits worth
  reporting, and if they do, the cell names the method the hit is really in.
- **`$` at the end is doing work.** It restricts the match to a declaration line
  whose signature closes on that line, which is what keeps a multi-line
  invocation like `Assert.Throws<T>(() =>` out. A method whose parameter list
  wraps is not matched, and its hits report `—`.
- **Allman bracing is handled; unindented bodies are not.** Scope is tracked by
  indentation, and a lone `{` on its own line is treated as the declaration above
  it continuing rather than as a sibling of it — without that, a C# class and
  method both close on the line after they open and every cell reports `—`. A
  file that does not indent bodies past their declaration is still outside what
  this can resolve, and reports `—` rather than a wrong name.
- **A pattern that does not compile is skipped with a warning**, not fatal. A
  broken row costs you the Test name column; the file and line stay exact.

If a project uses a base-class or source-generated test shape this table does not
match, the script reports `names=partial` and leaves those cells `—` rather than
guessing. That is the signal to add a row here.
