from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, HTTPException

from casewright.agents.case_knowledge_agent import CaseKnowledgeAgent
from casewright.core.models import ChatRequest, ChatResponse, ChatTurn
from casewright.repositories.chat_history import ChatHistoryRepository

router = APIRouter(tags=["chat"])


@lru_cache
def _get_agent() -> CaseKnowledgeAgent:
    return CaseKnowledgeAgent()


@lru_cache
def _get_history() -> ChatHistoryRepository:
    return ChatHistoryRepository()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="message must not be empty")

    _history = _get_history()
    _agent = _get_agent()
    history = await _history.get_turns(
        request.tenant_id, request.user_id, request.conversation_id
    )
    response = await _agent.answer(request, history)

    await _history.append_turns(
        request.tenant_id,
        request.user_id,
        request.conversation_id,
        [
            ChatTurn(role="user", content=request.message),
            ChatTurn(role="assistant", content=response.answer),
        ],
    )
    return response


@router.get("/chat/{conversation_id}", response_model=list[ChatTurn])
async def get_history(
    conversation_id: str, tenant_id: str = "default", user_id: str = "anonymous"
) -> list[ChatTurn]:
    return await _get_history().get_turns(tenant_id, user_id, conversation_id)
