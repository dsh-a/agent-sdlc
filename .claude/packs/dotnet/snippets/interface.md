# Interface / contract — C# idiom

> **Shape**: `.claude/agents/scaffold/interface.md`
> **Source**: extracted from the shipped template

```csharp
public interface IOrderRepository
{
    Task<Order?> GetByIdAsync(Guid id, CancellationToken ct = default);
    Task SaveAsync(Order order, CancellationToken ct = default);
}
```
