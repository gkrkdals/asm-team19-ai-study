import json
import re
import logging
from langchain_core.messages import HumanMessage
from agent.state import AgentState
from agent.domain import EXCEPTION_KEYWORDS
from agent.nodes.llm import get_llm

logger = logging.getLogger(__name__)


async def intent_classifier(state: AgentState) -> dict:
    """사용자 메시지에서 국가·목적·기간·직업을 추출하고 예외 상황을 감지한다."""
    llm = get_llm()
    last_message = state["messages"][-1].content

    detected_exception = None
    for kw, exc_type in EXCEPTION_KEYWORDS.items():
        if kw in last_message:
            detected_exception = exc_type
            break

    extraction_prompt = f"""다음 사용자 메시지에서 비자 관련 정보를 추출하세요.
이전 대화에서 파악된 정보도 고려하세요.

현재 파악된 정보:
- 국가: {state.get("country") or "미파악"}
- 목적: {state.get("purpose") or "미파악"}
- 기간: {state.get("duration") or "미파악"}
- 직업/분야: {state.get("profession") or "미파악"}

사용자 메시지: "{last_message}"

다음 JSON 형식으로만 응답하세요 (파악 불가 항목은 null):
{{
  "country": "US|JP|GB|CA|AU|DE 중 하나 또는 null",
  "purpose": "employment|study|travel|long_stay|working_holiday 중 하나 또는 null",
  "duration": "기간 문자열 또는 null",
  "profession": "직업/분야 또는 null",
  "has_sponsor": true|false|null
}}"""

    try:
        response = await llm.ainvoke([HumanMessage(content=extraction_prompt)])
        raw = response.content.strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        data = json.loads(match.group()) if match else {}
    except Exception as e:
        logger.warning("Intent extraction error: %s", e)
        data = {}

    resolved = {
        "country": data.get("country") or state.get("country"),
        "purpose": data.get("purpose") or state.get("purpose"),
        "duration": data.get("duration") or state.get("duration"),
        "profession": data.get("profession") or state.get("profession"),
        "has_sponsor": data.get("has_sponsor") if data.get("has_sponsor") is not None else state.get("has_sponsor"),
        "is_exception": bool(detected_exception),
        "exception_type": detected_exception or state.get("exception_type"),
    }

    detail = {
        "node": "intent_classifier",
        "headline": "자연어 → 구조화된 의도(JSON)",
        "items": [
            {"label": "① 사용자 요청(원문)", "value": last_message},
            {"label": "② LLM 추출 결과", "value": json.dumps(
                {k: resolved[k] for k in ("country", "purpose", "duration", "profession", "has_sponsor")},
                ensure_ascii=False,
            )},
            {"label": "③ 예외 키워드 감지", "value": detected_exception or "감지 안 됨"},
            {"label": "→ 다음 분기 근거", "value": _route_reason(resolved)},
        ],
    }

    return {**resolved, "node_details": [detail]}


def _route_reason(r: dict) -> str:
    if r["is_exception"]:
        return f"예외({r['exception_type']}) → exception_handler 로 이동"
    if r["country"] and r["purpose"]:
        return f"국가={r['country']}·목적={r['purpose']} 확보 → visa_rag_search 로 이동"
    return "국가/목적 부족 → response_formatter(재질문)으로 이동"
