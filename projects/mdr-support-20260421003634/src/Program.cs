using Microsoft.AspNetCore.Mvc;
using GeneratedApi.Models;
using GeneratedApi.Services;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();
builder.Services.AddProblemDetails();
// Application Insights -- reads APPLICATIONINSIGHTS_CONNECTION_STRING from env.
builder.Services.AddApplicationInsightsTelemetry();

// Domain services (in-memory for scaffold; swap for Cosmos / Azure OpenAI in production).
builder.Services.AddSingleton<DocumentIngestionService>();
builder.Services.AddSingleton<ExtractionService>();
builder.Services.AddSingleton<ClarificationService>();
builder.Services.AddSingleton<DraftRepository>();
builder.Services.AddSingleton<SessionService>();

// Upload size limit: 10 MB.
builder.Services.Configure<Microsoft.AspNetCore.Http.Features.FormOptions>(o =>
{
    o.MultipartBodyLengthLimit = 10 * 1024 * 1024;
});

var app = builder.Build();

if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.UseExceptionHandler();

// Liveness / readiness probes.
app.MapGet("/health", () => Results.Ok(new { status = "ok", timestamp = DateTimeOffset.UtcNow }));
app.MapGet("/health/ready", () => Results.Ok(new { status = "ready", timestamp = DateTimeOffset.UtcNow }));

var allowedExtensions = new HashSet<string> { ".txt", ".pdf", ".doc", ".docx", ".md" };

// Upload a document, extract structured data, return draft + open clarifications.
app.MapPost("/documents/upload", async (
    [FromForm] IFormFile file,
    [FromForm] string? notes,
    DocumentIngestionService ingestion,
    ExtractionService extraction,
    ClarificationService clarifier,
    DraftRepository repo) =>
{
    if (file is null || string.IsNullOrWhiteSpace(file.FileName))
        return Results.BadRequest(new { detail = "filename required" });
    var ext = Path.GetExtension(file.FileName).ToLowerInvariant();
    if (!string.IsNullOrEmpty(ext) && !allowedExtensions.Contains(ext))
        return Results.StatusCode(415);
    using var ms = new MemoryStream();
    await file.CopyToAsync(ms);
    var payload = ms.ToArray();
    var ingested = ingestion.Ingest(file.FileName, payload, notes ?? string.Empty);
    var result = extraction.Extract(ingested);
    var documentId = Guid.NewGuid().ToString();
    var draft = new ExtractionDraft(documentId, file.FileName, result.Fields, result.RawExcerpt);
    repo.Put(draft);
    var clarifications = clarifier.ComputeMissingFields(draft);
    return Results.Ok(new UploadResponse(documentId, clarifications, draft));
})
.DisableAntiforgery()
.WithName("UploadDocument")
.WithOpenApi();

// Human-in-the-loop chat turn: user answers a clarification, we merge into draft.
app.MapPost("/documents/{documentId}/chat", (
    string documentId,
    [FromBody] ChatRequest payload,
    ClarificationService clarifier,
    DraftRepository repo,
    SessionService sessions) =>
{
    var draft = repo.Get(documentId);
    if (draft is null) return Results.NotFound(new { detail = "document not found" });
    if (!string.IsNullOrEmpty(payload.Field))
    {
        draft.Fields[payload.Field] = payload.Answer;
        repo.Put(draft);
    }
    var clarifications = clarifier.ComputeMissingFields(draft);
    sessions.RecordTurn(documentId, payload.Field ?? "(free-form)", payload.Answer);
    return Results.Ok(new ChatResponse(documentId, draft, clarifications));
})
.WithName("ChatTurn")
.WithOpenApi();

// Retrieve current draft.
app.MapGet("/documents/{documentId}", (string documentId, DraftRepository repo) =>
{
    var draft = repo.Get(documentId);
    return draft is null ? Results.NotFound() : Results.Ok(draft);
})
.WithName("GetDocument")
.WithOpenApi();

// Poll open clarifications.
app.MapGet("/documents/{documentId}/clarifications", (
    string documentId,
    ClarificationService clarifier,
    DraftRepository repo) =>
{
    var draft = repo.Get(documentId);
    if (draft is null) return Results.NotFound();
    return Results.Ok(new ClarificationBundle(documentId, clarifier.ComputeMissingFields(draft)));
})
.WithName("GetClarifications")
.WithOpenApi();

// Finalize the draft -- 409 while mandatory fields remain.
app.MapPost("/documents/{documentId}/draft", (
    string documentId,
    ClarificationService clarifier,
    DraftRepository repo) =>
{
    var draft = repo.Get(documentId);
    if (draft is null) return Results.NotFound();
    var open = clarifier.ComputeMissingFields(draft);
    if (open.Count > 0)
        return Results.Conflict(new { message = "mandatory fields missing", clarifications = open });
    return Results.Ok(new DraftResponse(documentId, draft, DateTimeOffset.UtcNow));
})
.WithName("FinalizeDraft")
.WithOpenApi();

app.Logger.LogInformation("Starting generated extraction-chat API: Mdr Support");
app.Run();

public partial class Program { }
