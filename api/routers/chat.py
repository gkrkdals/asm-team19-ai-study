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
        "kb_written": None,
        "deep_search": False,
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


# ── 상황별 후속 질문 제안(AI 동적 생성) ───────────────────────────────────
class FollowupRequest(BaseModel):
    history: Optional[List[MessageItem]] = []
    country: Optional[str] = None
    purpose: Optional[str] = None


_FALLBACK_FOLLOWUPS = [
    "자격 요건을 더 자세히 알려줘",
    "필요 서류는 무엇인가요?",
    "처리 기간과 수수료가 궁금해요",
]


@router.post("/followups")
async def followups(req: FollowupRequest):
    """직전 대화 맥락을 바탕으로 사용자가 이어서 물을 만한 후속 질문을 LLM 으로 제안한다.

    ChatGPT 식 '예상 답변 칩'을 상황에 맞게 동적으로 구성하기 위한 엔드포인트.
    실패 시 일반 후속 질문으로 폴백한다.
    """
    import re
    import json as _json
    from agent.nodes.llm import get_llm

    convo = "\n".join(
        f"{m.role}: {m.content[:500]}" for m in (req.history or [])[-4:]
    ) or "(대화 없음)"
    ctx = []
    if req.country:
        ctx.append(f"국가={req.country}")
    if req.purpose:
        ctx.append(f"목적={req.purpose}")
    ctx_line = (" / ".join(ctx)) if ctx else "미상"

    prompt = f"""당신은 해외 비자 상담의 '후속 질문 제안기'입니다.
아래 대화를 보고, 사용자가 자연스럽게 '이어서' 물어볼 만한 **서로 다른** 후속 질문 4개를
한국어로 제안하세요.

요건:
- 각 질문은 12~24자 내외로 짧고 구체적으로.
- 대화 맥락(국가·목적·언급된 비자/예외)을 반영해 실제로 도움이 되는 질문으로.
- 서로 겹치지 않게 다양한 측면(요건/서류/절차/기간/비용/대안비자/영주권 전환/주의사항 등)을 다룸.
- 비자와 무관한 잡담이면 비자 관련으로 유도하는 질문을 제안.

맥락: {ctx_line}
대화:
{convo}

JSON 배열로만 출력(설명 금지): ["질문1","질문2","질문3","질문4"]"""

    try:
        llm = get_llm(temperature=0.4)
        resp = await llm.ainvoke([HumanMessage(content=prompt)])
        match = re.search(r"\[.*\]", resp.content or "", re.DOTALL)
        arr = _json.loads(match.group()) if match else []
        suggestions = [str(s).strip() for s in arr if str(s).strip()][:4]
    except Exception as e:  # noqa: BLE001
        logger.warning("followups generation error: %s", e)
        suggestions = []

    if not suggestions:
        suggestions = list(_FALLBACK_FOLLOWUPS)
    return {"suggestions": suggestions}
