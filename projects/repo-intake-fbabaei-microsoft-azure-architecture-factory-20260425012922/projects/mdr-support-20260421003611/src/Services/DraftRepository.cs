namespace GeneratedApi.Services;

using System.Collections.Concurrent;
using GeneratedApi.Models;

// In-memory repository -- swap for Cosmos DB / Azure SQL in production.
public class DraftRepository
{
    private readonly ConcurrentDictionary<string, ExtractionDraft> _store = new();

    public void Put(ExtractionDraft draft) => _store[draft.DocumentId] = draft;

    public ExtractionDraft? Get(string documentId)
        => _store.TryGetValue(documentId, out var draft) ? draft : null;

    public IReadOnlyList<string> ListIds() => _store.Keys.ToList();
}
