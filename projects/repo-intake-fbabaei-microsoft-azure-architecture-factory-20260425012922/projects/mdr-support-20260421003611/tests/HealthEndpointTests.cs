using System.Net;
using FluentAssertions;
using Microsoft.AspNetCore.Mvc.Testing;
using Xunit;

public class HealthEndpointTests : IClassFixture<WebApplicationFactory<Program>>
{
    private readonly WebApplicationFactory<Program> _factory;

    public HealthEndpointTests(WebApplicationFactory<Program> factory) { _factory = factory; }

    [Fact]
    public async Task Health_Returns_Ok()
    {
        var client = _factory.CreateClient();
        var response = await client.GetAsync("/health");
        response.StatusCode.Should().Be(HttpStatusCode.OK);
    }

    [Fact]
    public async Task HealthReady_Returns_Ok()
    {
        var client = _factory.CreateClient();
        var response = await client.GetAsync("/health/ready");
        response.StatusCode.Should().Be(HttpStatusCode.OK);
    }

    [Fact]
    public async Task GetUnknownDocument_Returns_NotFound()
    {
        var client = _factory.CreateClient();
        var response = await client.GetAsync("/documents/does-not-exist");
        response.StatusCode.Should().Be(HttpStatusCode.NotFound);
    }
}
