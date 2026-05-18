namespace GeneratedApi.Services;

using GeneratedApi.Models;

public class ClarificationService
{
    private static readonly Dictionary<string, string> FieldPrompts = new()
    {
        ["reference_id"] = "What is the reference ID for this submission?",
        ["submission_date"] = "What is the submission date (YYYY-MM-DD)?",
        ["jurisdiction"] = "Which jurisdiction does this arrangement apply to?",
        ["summary"] = "Please provide a short summary of the arrangement.",
    };

    public List<Clarification> ComputeMissingFields(ExtractionDraft draft)
    {
        var missing = new List<Clarification>();
        foreach (var field in ExtractionService.MandatoryFields)
        {
            draft.Fields.TryGetValue(field, out var value);
            if (string.IsNullOrWhiteSpace(value))
            {
                var prompt = FieldPrompts.TryGetValue(field, out var p)
                    ? p
                    : $"Please provide a value for '{field}'.";
                missing.Add(new Clarification(field, prompt));
            }
        }
        return missing;
    }
}
