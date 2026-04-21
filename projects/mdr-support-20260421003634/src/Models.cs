namespace GeneratedApi.Models;

public record Clarification(string Field, string Prompt);

public record ExtractionDraft(
    string DocumentId,
    string SourceFilename,
    Dictionary<string, string?> Fields,
    string RawExcerpt
);

public record ExtractionResult(Dictionary<string, string?> Fields, string RawExcerpt);

public record UploadResponse(string DocumentId, List<Clarification> Clarifications, ExtractionDraft Draft);

public record ChatRequest(string? Field, string Answer);

public record ChatResponse(string DocumentId, ExtractionDraft Draft, List<Clarification> Clarifications);

public record ClarificationBundle(string DocumentId, List<Clarification> Clarifications);

public record DraftResponse(string DocumentId, ExtractionDraft Draft, DateTimeOffset FinalizedAt);
