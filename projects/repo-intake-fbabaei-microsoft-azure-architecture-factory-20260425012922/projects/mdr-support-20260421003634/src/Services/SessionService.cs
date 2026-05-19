namespace GeneratedApi.Services;

using System.Collections.Concurrent;

public record ChatTurn(DateTimeOffset At, string Field, string Answer);

public record Session(string DocumentId, List<ChatTurn> Turns);

public class SessionService
{
    private readonly ConcurrentDictionary<string, Session> _sessions = new();

    public void RecordTurn(string documentId, string field, string answer)
    {
        var session = _sessions.GetOrAdd(documentId, id => new Session(id, new List<ChatTurn>()));
        lock (session.Turns)
        {
            session.Turns.Add(new ChatTurn(DateTimeOffset.UtcNow, field, answer));
        }
    }

    public Session? Get(string documentId)
        => _sessions.TryGetValue(documentId, out var session) ? session : null;
}
