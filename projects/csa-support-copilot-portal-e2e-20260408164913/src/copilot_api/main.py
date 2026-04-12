from datetime import datetime, timezone
from fastapi import FastAPI

from .models import AskRequest, AskResponse
from .services.copilot_service import build_response


app = FastAPI(title="CSA Support Copilot API", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.post("/api/copilot/ask", response_model=AskResponse)
def ask_copilot(payload: AskRequest) -> AskResponse:
    guidance = build_response(payload.question, payload.context)
    return AskResponse(answer=guidance, source="generated-starter")
