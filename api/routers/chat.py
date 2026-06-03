from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional
from langchain_core.messages import HumanMessage, AIMessage
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


def get_graph():
    from agent.graph import get_graph as _get_graph
    return _get_graph()


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


def build_initial_state(message: str, history: Optional[List[MessageItem]] = None) -> dict:
    """채팅/스트리밍이 공유하는 LangGraph 초기 State 빌더."""
    messages = []
    for m in (history or []):
        if m.role == "user":
            messages.append(HumanMessage(content=m.content))
        else:
            messages.append(AIMessage(content=m.content))
    messages.append(HumanMessage(content=message))

    return {
        "messages": messages,
        "country": None,
        "purpose": None,
        "duration": None,
        "profession": None,
        "has_sponsor": None,
        "is_exception": False,
        "exception_type": None,
        "is_visa_related": True,
        "search_results": None,
        "extra_context": None,
        "web_query": None,
        "search_attempts": 0,
        "search_quality": None,
        "final_response": None,
        "node_details": [],
    }


@router.post("/", response_model=ChatResponse)
async def chat(req: ChatRequest):
    graph = get_graph()

    initial_state = build_initial_state(req.message, req.history)

    try:
        result = await graph.ainvoke(initial_state)
        response = result.get("final_response") or "죄송합니다. 응답을 생성하지 못했습니다."
    except Exception as e:
        logger.error(f"Agent invocation error: {e}")
        response = f"⚠️ 오류가 발생했습니다: {str(e)}"

    return ChatResponse(response=response, session_id=req.session_id or "default")
