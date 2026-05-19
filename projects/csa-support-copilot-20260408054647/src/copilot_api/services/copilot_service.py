def build_response(question: str, context: str) -> tuple[str, list[str], list[str]]:
    summary = context.strip()[:240]
    tools_used = ["kb-search", "runbook-assistant"]
    citations = ["internal://csa/runbooks", "internal://csa/knowledge-base"]

    if summary:
        return (
            "Starter copilot response for question: '" + question +
            "'. Context summary: " + summary +
            ". Replace this logic with your MCP orchestration and enterprise knowledge retrieval.",
            tools_used,
            citations,
        )
    return (
        "Starter copilot response for question: '" + question +
        "'. Replace this logic with your MCP orchestration and enterprise knowledge retrieval.",
        tools_used,
        citations,
    )
