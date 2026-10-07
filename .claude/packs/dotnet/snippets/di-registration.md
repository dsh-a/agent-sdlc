# DI registration — C# idiom

> **Shape**: `cross-cutting — every pattern file's § Wiring points here`
> **Source**: extracted from the shipped template

```csharp
services.AddScoped<IOrderRepository, OrderRepository>();
services.AddScoped<PlaceOrderHandler>();
```

> Codegen: .NET typically has no separate codegen step. If yours does (e.g. source
> generators, `dotnet ef migrations`), set it as the **Code generation** command in
> `.omp/agent-config.md` § Project Commands.
