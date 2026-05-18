namespace GeneratedApi.Services;

using System.Text.RegularExpressions;
using GeneratedApi.Models;

public class ExtractionService
{
    // Mandatory domain fields the clarification loop expects.
    public static readonly string[] MandatoryFields =
    {
        "reference_id",
        "submission_date",
        "jurisdiction",
        "summary",
    };

    public ExtractionResult Extract(IngestedDocument doc)
    {
        var text = doc.TextExcerpt ?? string.Empty;
        var fields = new Dictionary<string, string?>();

        var ref_ = Regex.Match(text, @"\b(?:ref|reference)\s*[:#]?\s*([A-Z0-9\-]{4,})", RegexOptions.IgnoreCase);
        if (ref_.Success) fields["reference_id"] = ref_.Groups[1].Value;

        var date = Regex.Match(text, @"\b(20\d{2}-\d{2}-\d{2})\b");
        if (date.Success) fields["submission_date"] = date.Groups[1].Value;

        var jur = Regex.Match(text, @"\bjurisdiction\s*[:=]?\s*([A-Za-z ]{2,40})", RegexOptions.IgnoreCase);
        if (jur.Success) fields["jurisdiction"] = jur.Groups[1].Value.Trim();

        if (text.Length > 0) fields["summary"] = text.Length > 200 ? text[..200] : text;

        return new ExtractionResult(fields, text.Length > 500 ? text[..500] : text);
    }
}
