namespace GeneratedApi.Services;

public record IngestedDocument(string Filename, string ContentType, string TextExcerpt, string Notes);

public class DocumentIngestionService
{
    // Swap this stub for Azure AI Document Intelligence / Form Recognizer.
    public IngestedDocument Ingest(string filename, byte[] payload, string notes = "")
    {
        var lowered = filename.ToLowerInvariant();
        string contentType;
        string textExcerpt;
        if (lowered.EndsWith(".pdf"))
        {
            contentType = "application/pdf";
            textExcerpt = $"[pdf: {payload.Length} bytes -- replace ingestion stub with OCR]";
        }
        else if (lowered.EndsWith(".doc") || lowered.EndsWith(".docx"))
        {
            contentType = "application/msword";
            textExcerpt = $"[word doc: {payload.Length} bytes -- replace ingestion stub]";
        }
        else
        {
            contentType = "text/plain";
            var decoded = System.Text.Encoding.UTF8.GetString(payload);
            textExcerpt = decoded.Length > 2000 ? decoded[..2000] : decoded;
        }
        return new IngestedDocument(filename, contentType, textExcerpt, notes);
    }
}
