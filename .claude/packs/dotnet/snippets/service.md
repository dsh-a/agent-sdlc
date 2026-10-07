# Service — C# idiom

> **Shape**: `.claude/agents/scaffold/service.md`
> **Source**: extracted from the shipped template

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
