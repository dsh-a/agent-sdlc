using Xunit;

public sealed class FooRepositoryTests
{
    private readonly FooRepository _repo = new FooRepository();

    [Fact]
    public async Task InsertsRow()
    {
        await _repo.Insert(new Foo());
        Assert.Equal(1, _repo.Count);
    }

    [Fact]
    public void ReturnsNullOnMissing()
    {
        Assert.Null(_repo.Find("nope"));
    }
}
