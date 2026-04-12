def build_response(question: str, context: str) -> str:
    summary = context.strip()[:240]
    if summary:
        return (
            "Starter copilot response for question: '" + question +
            "'. Context summary: " + summary +
            ". Replace this logic with your MCP orchestration and enterprise knowledge retrieval."
        )
    return (
        "Starter copilot response for question: '" + question +
        "'. Replace this logic with your MCP orchestration and enterprise knowledge retrieval."
    )
