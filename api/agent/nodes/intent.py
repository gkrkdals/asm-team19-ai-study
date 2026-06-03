import json
import re
import logging
from langchain_core.messages import HumanMessage
from agent.state import AgentState
from agent.domain import EXCEPTION_KEYWORDS, VISA_KEYWORDS
from agent.nodes.llm import get_intent_llm

logger = logging.getLogger(__name__)


def _recent_transcript(messages, limit: int = 6) -> str:
    """직전 대화 몇 턴을 'User/AI' 형태의 간단한 트랜스크립트로 만든다(현재 메시지 제외)."""
    prior = list(messages[:-1])[-limit:]
    lines = []
    for m in prior:
        role = "User" if m.__class__.__name__ == "HumanMessage" else "AI"
        text = (m.content or "").replace("\n", " ")[:160]
        lines.append(f"{role}: {text}")
    return "\n".join(lines) if lines else "(이전 대화 없음)"


async def intent_classifier(state: AgentState) -> dict:
    """사용자 메시지에서 국가·목적·기간·직업을 추출하고 예외 상황을 감지한다."""
    llm = get_intent_llm()  # temperature=0 결정적 추출, INTENT_MODEL 로 교체 가능
    last_message = state["messages"][-1].content
    transcript = _recent_transcript(state["messages"])

    detected_exception = None
    _msg_lower = last_message.lower()
    for kw, exc_type in EXCEPTION_KEYWORDS.items():
        if kw.lower() in _msg_lower:
            detected_exception = exc_type
            break

    extraction_prompt = f"""다음 사용자 메시지에서 비자 관련 정보를 추출하세요.
아래 '이전 대화'의 맥락을 반드시 고려하세요. 최신 사용자 메시지가 국가만 바꾸고(예: "그럼 영국은?")
목적/직업을 생략했다면, 이전 대화의 목적/직업을 이어받아 채우세요.

이전 대화:
{transcript}

세션에 기록된 정보:
- 국가: {state.get("country") or "미파악"}
- 목적: {state.get("purpose") or "미파악"}
- 기간: {state.get("duration") or "미파악"}
- 직업/분야: {state.get("profession") or "미파악"}

최신 사용자 메시지: "{last_message}"

다음 JSON 형식으로만 응답하세요 (파악 불가 항목은 null):
{{
  "country": "ISO 3166-1 alpha-2 국가코드(예: US, JP, GB, CA, AU, DE, FR, TH, ZA …) 또는 null",
  "purpose": "employment|study|travel|long_stay|working_holiday 중 하나 또는 null",
  "duration": "기간 문자열 또는 null",
  "profession": "직업/분야 또는 null",
  "has_sponsor": true|false|null,
  "is_visa_related": true|false
}}

판단 기준:
- is_visa_related: 해외 비자·체류·취업/유학/여행/이민·입국·여권 관련이면 반드시 true.
  '취업/유학/체류/이민/입국'처럼 해외 이동을 함의하는 표현이 있으면 true 로 판단하세요.
  순수한 잡담(날씨·음식·인사 등)만 false.

예시:
- "캐나다에서 소프트웨어 개발자로 취업하고 싶어요" → {{"country":"CA","purpose":"employment","profession":"소프트웨어 개발자","is_visa_related":true}}
- "일본 유학 비자 알려줘" → {{"country":"JP","purpose":"study","is_visa_related":true}}
- "남아공에서 일하려면?" → {{"country":"ZA","purpose":"employment","is_visa_related":true}}
- "오늘 점심 뭐 먹지?" → {{"country":null,"purpose":null,"is_visa_related":false}}"""

    try:
        response = await llm.ainvoke([HumanMessage(content=extraction_prompt)])
        raw = response.content.strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        data = json.loads(match.group()) if match else {}
    except Exception as e:
        logger.warning("Intent extraction error: %s", e)
        data = {}

    # 멀티턴: 국가가 바뀌면(예: 캐나다→영국) 이전 국가에 묶인 직업/기간/스폰서 정보는 폐기
    new_country = (data.get("country") or "").upper() or None
    prev_country = state.get("country")
    country_changed = bool(new_country and prev_country and new_country != prev_country)

    if country_changed:
        profession = data.get("profession")
        duration = data.get("duration")
        has_sponsor = data.get("has_sponsor")
    else:
        profession = data.get("profession") or state.get("profession")
        duration = data.get("duration") or state.get("duration")
        has_sponsor = data.get("has_sponsor") if data.get("has_sponsor") is not None else state.get("has_sponsor")

    # 비자 관련 여부: 강한 신호(국가/목적/예외/세션맥락)나 도메인 키워드가 있으면
    # LLM 판단을 무시하고 비자 관련으로 강제(오분류 방지). 순수 잡담만 general_chat.
    keyword_hit = any(k in _msg_lower for k in VISA_KEYWORDS)
    has_signal = bool(new_country or data.get("purpose") or detected_exception
                      or state.get("country") or state.get("purpose"))
    llm_says = data.get("is_visa_related")
    if has_signal or keyword_hit:
        is_visa_related = True
    elif llm_says is True:
        is_visa_related = True
    else:
        is_visa_related = False

    resolved = {
        "country": new_country or state.get("country"),
        "purpose": data.get("purpose") or state.get("purpose"),
        "duration": duration,
        "profession": profession,
        "has_sponsor": has_sponsor,
        "is_exception": bool(detected_exception),
        "exception_type": detected_exception or state.get("exception_type"),
        "is_visa_related": bool(is_visa_related),
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
            {"label": "③ 비자 관련 여부", "value": "예" if resolved["is_visa_related"] else "아니오(일반 대화)"},
            {"label": "④ 예외 키워드 감지", "value": detected_exception or "감지 안 됨"},
            {"label": "⑤ 국가 전환", "value": f"{prev_country}→{new_country} (맥락 초기화)" if country_changed else "없음"},
            {"label": "→ 다음 분기 근거", "value": _route_reason(resolved)},
        ],
    }

    return {**resolved, "node_details": [detail]}


def _route_reason(r: dict) -> str:
    if not r["is_visa_related"]:
        return "비자 무관 질문 → general_chat 로 이동"
    if r["is_exception"]:
        return f"예외({r['exception_type']}) → exception_handler 로 이동"
    if r["country"] and r["purpose"]:
        return f"국가={r['country']}·목적={r['purpose']} 확보 → visa_rag_search 로 이동"
    return "국가/목적 부족 → response_formatter(재질문)으로 이동"
