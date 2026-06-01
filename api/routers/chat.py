from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional
from langchain_core.messages import HumanMessage, AIMessage
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

_graph = None


def get_graph():
    global _graph
    if _graph is None:
        from agent.graph import build_graph
        _graph = build_graph()
    return _graph


class MessageItem(BaseModel):
    role: str   # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"
    history: Optional[List[MessageItem]] = []


class ChatResponse(BaseModel):
    response: str
    session_id: str


@router.post("/", response_model=ChatResponse)
async def chat(req: ChatRequest):
    graph = get_graph()

    messages = []
    for m in (req.history or []):
        if m.role == "user":
            messages.append(HumanMessage(content=m.content))
        else:
            messages.append(AIMessage(content=m.content))
    messages.append(HumanMessage(content=req.message))

    initial_state = {
        "messages": messages,
        "country": None,
        "purpose": None,
        "duration": None,
        "profession": None,
        "has_sponsor": None,
        "is_exception": False,
        "exception_type": None,
        "search_results": None,
        "final_response": None,
    }

    try:
        result = await graph.ainvoke(initial_state)
        response = result.get("final_response") or "죄송합니다. 응답을 생성하지 못했습니다."
    except Exception as e:
        logger.error(f"Agent invocation error: {e}")
        response = f"⚠️ 오류가 발생했습니다: {str(e)}"

    return ChatResponse(response=response, session_id=req.session_id or "default")
