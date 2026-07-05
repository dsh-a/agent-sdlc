# .NET Test Patterns (pack: dotnet)

> Placeholder defaults for the `dotnet` pack. Adjust to your test framework.

- **Framework:** _[xUnit (default) | NUnit | MSTest]_. Mocking: _[Moq | NSubstitute | FakeItEasy]_.
- **Naming:** `MethodUnderTest_Scenario_ExpectedResult` or your team's convention.
- **Structure:** Arrange / Act / Assert, one logical assertion target per test.
- **Test path:** mirror source under `tests/` (e.g. `src/Orders/OrderService.cs` →
  `tests/Orders.Tests/OrderServiceTests.cs`). Configure the test glob in
  `.claude/config.md` § Project Commands.
- **Fixtures:** share setup via `IClassFixture<T>` / collection fixtures / builders; do not
  re-instantiate dependencies in every test.
- **Async:** test `async` code with `async Task` tests and `await` — never `.Result`/`.Wait()`.
- **Data-layer tests:** prefer an in-memory or testcontainer database over mocking the
  `DbContext` when verifying queries/constraints.
