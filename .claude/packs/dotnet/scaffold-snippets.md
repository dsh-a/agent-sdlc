# .NET Scaffold Snippets (pack: dotnet)

> Placeholder language snippets the `scaffold` agent uses when generating new components.
> The pattern *shapes* (interface, service, facade, use-case, command, strategy, observer)
> are defined language-neutrally in `.claude/agents/scaffold/*.md`; this file supplies the
> C# idiom for each. Fill in to match your stack.

## Interface / contract

```csharp
public interface IOrderRepository
{
    Task<Order?> GetByIdAsync(Guid id, CancellationToken ct = default);
    Task SaveAsync(Order order, CancellationToken ct = default);
}
```

## Service / use case (constructor injection)

```csharp
public sealed class PlaceOrderHandler
{
    private readonly IOrderRepository _orders;
    private readonly ILogger<PlaceOrderHandler> _log;

    public PlaceOrderHandler(IOrderRepository orders, ILogger<PlaceOrderHandler> log)
    {
        _orders = orders;
        _log = log;
    }

    public async Task<Result> HandleAsync(PlaceOrder command, CancellationToken ct = default)
    {
        // ...
    }
}
```

## DI registration

```csharp
services.AddScoped<IOrderRepository, OrderRepository>();
services.AddScoped<PlaceOrderHandler>();
```

> Codegen: .NET typically has no separate codegen step. If yours does (e.g. source
> generators, `dotnet ef migrations`), set it as the **Code generation** command in
> `.claude/config.md` § Project Commands.
