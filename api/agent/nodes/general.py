import logging
from langchain_core.messages import SystemMessage
from agent.state import AgentState
from agent.nodes.llm import get_llm

logger = logging.getLogger(__name__)

_GENERAL_PROMPT = """당신은 해외 비자 안내 AI 'VisaGuide AI'입니다.
지금 사용자의 메시지는 비자·체류·입국과 직접 관련이 없는 일반적인 질문/대화입니다.

지침:
- 짧고 친근하게(2~4문장) 응답하되, 비자 도메인 밖의 전문적 답변은 피하세요.
- 자연스럽게 본 서비스의 역할(해외 비자 추천·요건·서류·예외 안내)로 대화를 유도하세요.
- 지원 국가/주제 예시를 한 줄 덧붙이세요: 🇺🇸미국 🇯🇵일본 🇬🇧영국 🇨🇦캐나다 🇦🇺호주 🇩🇪독일 (그 외 국가는 웹검색)."""


async def general_chat(state: AgentState) -> dict:
    """비자와 무관한 일반 질문을 간단히 응대하고 비자 도메인으로 유도한다."""
    llm = get_llm()
    last_msg = state["messages"][-1].content

    detail = {
        "node": "general_chat",
        "headline": "비자 무관 질문 — 일반 응대 + 도메인 유도",
        "items": [
            {"label": "① 사용자 요청", "value": last_msg},
            {"label": "② 처리", "value": "비자 워크플로(RAG/검색) 미진입 → 일반 응답 노드에서 처리"},
        ],
    }

    try:
        response = await llm.ainvoke(
            [SystemMessage(content=_GENERAL_PROMPT)] + list(state["messages"])
        )
        return {"final_response": response.content, "node_details": [detail]}
    except Exception as e:  # noqa: BLE001
        logger.error("general_chat error: %s", e)
        return {
            "final_response": (
                "저는 해외 **비자 안내**를 돕는 VisaGuide AI예요. 🛂\n\n"
                "어느 나라에서, 얼마나, 무슨 목적(취업·유학·여행·장기체류)으로 체류하실지 알려주시면 "
                "맞는 비자를 찾아드릴게요.\n\n"
                "> 지원: 🇺🇸미국 · 🇯🇵일본 · 🇬🇧영국 · 🇨🇦캐나다 · 🇦🇺호주 · 🇩🇪독일 (그 외 국가는 웹검색 대응)"
            ),
            "node_details": [detail],
        }
