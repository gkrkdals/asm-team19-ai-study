import json
import re
import logging
from langchain_core.messages import HumanMessage
from agent.state import AgentState
from agent.domain import (
    EXCEPTION_KEYWORDS, VISA_KEYWORDS, detect_country, detect_purpose, is_deep_search,
)
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

    # ── 감탄사/반응/잡담 조기 감지 (LLM 호출 전) ──────────────────────────
    # "뭐야 로또잖아;", "고마워요", "진짜요?" 처럼 비자 키워드가 없고 30자 이하인
    # 단순 반응·감탄사·인사는 바로 general_chat 으로 분기한다.
    # (LLM 이 대화 맥락을 보고 '비자 관련' 으로 오분류하는 패턴 차단)
    _REACTION_PATTERNS = [
        r"^(뭐야|진짜|헐|대박|와[.!;]*|어머|아이고|완전히|로또|ㄷㄷ|ㅎㄷㄷ|실화냐|미쳤[다어]|미칠)",
        r"^(감사|고마|고맙|천만에|괜찮|별말씀|ㄳ|감사합니다|고맙습니다)[.!요]*$",
        r"^(ㅋ{2,}|ㄷ{2,}|ㅎ{2,}|!{2,})[.!;]*$",
        r"^(알겠|알겠습니다|알겠어요|넵|네\s*알겠|ㅇㅋ|오케이|ok|okay)[.!;]*$",
    ]
    _msg_strip = last_message.strip()
    _no_visa_kw = not any(k in last_message.lower() for k in VISA_KEYWORDS)
    _short_enough = len(_msg_strip) <= 40
    _is_reaction = _no_visa_kw and _short_enough and any(
        re.search(p, _msg_strip, re.IGNORECASE) for p in _REACTION_PATTERNS
    )
    if _is_reaction:
        logger.info("intent: reaction/casual detected, short-circuit → general_chat")
        detail = {"node": "intent_classifier",
                  "headline": "자연어 → 구조화된 의도(JSON)",
                  "items": [{"label": "① 사용자 요청(원문)", "value": last_message},
                             {"label": "② 분류 근거", "value": "감탄사/반응/잡담 패턴 감지 → general_chat"},
                             {"label": "③ 비자 관련 여부", "value": "아니오 → 일반 대화 분기"},
                             {"label": "→ 다음 분기 근거", "value": "비자 무관 질문 → general_chat 로 이동"}]}
        return {"is_visa_related": False, "node_details": [detail]}
    # ─────────────────────────────────────────────────────────────────────

    detected_exception = None
    _msg_lower = last_message.lower()

    # ── 화살표 패턴 우선 감지: "A → B" 형태로 비자 상태 전환을 명시한 경우 ──
    # 예: "관광 → 취업", "학생 → 워킹홀리데이", "취업비자 → 영주권"
    # (EXCEPTION_KEYWORDS 에도 일부 추가했지만, 조합이 무한하므로 regex 로 보완)
    _ARROW_STATUS_CHANGE_RE = re.compile(
        r"(관광|여행|학생|유학|취업|워킹홀리데이|워홀|취업비자|학생비자|관광비자)"
        r"\s*[→\->]\s*"
        r"(취업|영주|영주권|유학|워킹홀리데이|정착|이민)",
        re.IGNORECASE
    )
    if not detected_exception and _ARROW_STATUS_CHANGE_RE.search(last_message):
        detected_exception = "status_change"
        logger.info("intent: arrow-pattern status_change detected: %s", last_message[:60])

    # ── 상충/수정 신호 감지: "아니", "사실은", "그게 아니라" → 이전 맥락 무시하고 새 신호 우선 ──
    # 예: "아니 유학만 하고 싶어" → 이전 취업 의도 무효화, 유학이 최신 신호
    # 예: "관광이 아니라 취업" → 관광 무효, 취업만 유효
    _NEGATION_RE = re.compile(r"(아니|사실은|그게 아니라|아니였|다시 생각해보니|아 미안|실수했)", re.IGNORECASE)
    if _NEGATION_RE.search(last_message):
        # 이전 대화 컨텍스트 무시 신호 → state 필드 부분 리셋
        logger.info("intent: negation/override detected, prioritize current message signals only")
        # 다음 명령어: prompt 에 '이전 대화 무시, 현재 메시지만 사용' 추가 (LLM 레벨)

    for kw, exc_type in EXCEPTION_KEYWORDS.items():
        if kw.lower() in _msg_lower:
            detected_exception = exc_type
            break

    # ③ 수정 신호 적용: 메시지에 "아니", "사실은" 등이 있으면 이전 대화 무시하고 현재만 추출
    override_flag = _NEGATION_RE.search(last_message) if "_NEGATION_RE" in locals() else False
    context_instruction = (
        "최신 사용자 메시지만 해석하세요. 이전 대화는 무시합니다(사용자가 정정/취소했으므로)."
        if override_flag
        else "최신 사용자 메시지가 국가만 바꾸고(예: '그럼 영국은?') 목적/직업을 생략했다면, "
             "이전 대화의 목적/직업을 이어받아 채우세요."
    )

    extraction_prompt = f"""다음 사용자 메시지에서 비자 관련 정보를 추출하세요.
{context_instruction}

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
  "is_visa_related": true|false,
  "is_followup": true|false
}}

판단 기준:
- country/purpose: 메시지에 국가명(캐나다·미국·일본·영국·호주·독일·프랑스·남아공 등)이나
  목적(취업·유학·여행·이민·워킹홀리데이 등)이 **명시되어 있으면 절대 null 로 두지 말고
  반드시 코드/값으로 채우세요**. 예) "캐나다에서 …취업" → country="CA", purpose="employment".
- is_visa_related: 해외 비자·체류·취업/유학/여행/이민·입국·여권 관련이면 반드시 true.
  '취업/유학/체류/이민/입국'처럼 해외 이동을 함의하는 표현이 있으면 true 로 판단하세요.
  순수한 잡담(날씨·음식·인사 등)만 false.
- is_followup: **이전 대화에서 이미 국가·목적(또는 특정 비자)이 정해진 뒤** 그 비자에 대한
  추가·상세·후속 질문(필요서류·처리기간·비용·연장·특정 비자코드 상세·"스폰서 협의" 등 액션)이면 true.
  **새로운 국가/목적의 비자를 처음 추천받으려는 요청**(예: "미국 취업하고 싶어", "그럼 영국은?")은 false.
  이전 대화가 없으면(첫 질문) 항상 false.

예시:
- "캐나다에서 소프트웨어 개발자로 취업하고 싶어요" → {{"country":"CA","purpose":"employment","profession":"소프트웨어 개발자","is_visa_related":true,"is_followup":false}}
- "일본 유학 비자 알려줘" → {{"country":"JP","purpose":"study","is_visa_related":true,"is_followup":false}}
- "남아공에서 일하려면?" → {{"country":"ZA","purpose":"employment","is_visa_related":true,"is_followup":false}}
- "오늘 점심 뭐 먹지?" → {{"country":null,"purpose":null,"is_visa_related":false,"is_followup":false}}
- (직전 대화에서 미국 취업 H-1B 안내를 받은 뒤) "H-1B 신청 시 추가 서류는?" → {{"country":"US","purpose":"employment","is_visa_related":true,"is_followup":true}}
- (직전 대화에서 미국 취업 안내 후) "고용주와 스폰서 협의" → {{"country":"US","purpose":"employment","is_visa_related":true,"is_followup":true}}"""

    try:
        response = await llm.ainvoke([HumanMessage(content=extraction_prompt)])
        raw = response.content.strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        data = json.loads(match.group()) if match else {}
    except Exception as e:
        logger.warning("Intent extraction error: %s", e)
        data = {}

    # 키워드 폴백: LLM 이 null/오류를 반환해도 메시지에서 직접 국가·목적을 보강한다.
    # (워크플로 결정성 — is_visa_related 휴리스틱과 동일한 철학. LLM 변동성에 견고)
    kw_country = detect_country(last_message)
    kw_purpose = detect_purpose(last_message)

    # 멀티턴: 국가가 바뀌면(예: 캐나다→영국) 이전 국가에 묶인 직업/기간/스폰서 정보는 폐기
    llm_country = (data.get("country") or "").upper() or None
    new_country = llm_country or kw_country
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

    # 비자 관련 여부: 현재 메시지에서 강한 신호가 있거나 도메인 키워드가 있으면
    # LLM 판단을 무시하고 비자 관련으로 강제. 이전 세션 맥락(state.country/purpose)은
    # '이 메시지가 비자 질문인가' 판단에 사용하지 않는다.
    # (예: "뭐야 로또잖아;", "고마워요" 같은 반응/잡담은 general_chat으로 정확히 분기)
    keyword_hit = any(k in _msg_lower for k in VISA_KEYWORDS)
    # ← 핵심 수정: 현재 메시지 신호만(이전 세션 state 제외)
    cur_signal = bool(new_country or data.get("purpose") or kw_purpose or detected_exception)
    llm_says = data.get("is_visa_related")
    if cur_signal or keyword_hit:
        is_visa_related = True
    elif llm_says is True:
        # LLM 이 비자 관련이라고 명시적으로 판단한 경우만 허용
        is_visa_related = True
    else:
        is_visa_related = False

    # 후속/상세 질문: 이전 대화가 있고(첫 질문 아님) 비자 관련이며 LLM 이 후속이라 판단하면 true.
    # (새 추천이 아니라 기존 비자에 대한 추가 질문 → 프론트가 라이트 카드로 표시)
    has_prior = len(state["messages"]) > 1
    is_followup = bool(is_visa_related and has_prior and data.get("is_followup"))

    deep = is_deep_search(last_message)

    resolved = {
        "country": new_country or state.get("country"),
        "purpose": data.get("purpose") or kw_purpose or state.get("purpose"),
        "duration": duration,
        "profession": profession,
        "has_sponsor": has_sponsor,
        "is_exception": bool(detected_exception),
        "exception_type": detected_exception or state.get("exception_type"),
        "is_visa_related": bool(is_visa_related),
        "is_followup": is_followup,
        "deep_search": bool(deep),
    }

    # 폴백 사용 여부(트레이스 투명성): LLM 이 비웠지만 키워드로 보강했는지 표시
    fb_parts = []
    if not llm_country and kw_country:
        fb_parts.append(f"국가={kw_country}")
    if not data.get("purpose") and kw_purpose:
        fb_parts.append(f"목적={kw_purpose}")
    fallback_note = ("키워드 보강: " + ", ".join(fb_parts)) if fb_parts else "사용 안 함(LLM 추출 충분)"
    # 비자 분류 근거: 어떤 신호를 봤는지 명시(디버깅용)
    vis_reason = ("현재 메시지 국가/목적/예외 신호" if cur_signal else
                  ("도메인 키워드 감지" if keyword_hit else
                   ("LLM 판단" if llm_says is True else "신호 없음 → 일반 대화")))

    detail = {
        "node": "intent_classifier",
        "headline": "자연어 → 구조화된 의도(JSON)",
        "items": [
            {"label": "① 사용자 요청(원문)", "value": last_message},
            {"label": "② 추출 결과(LLM+키워드)", "value": json.dumps(
                {k: resolved[k] for k in ("country", "purpose", "duration", "profession", "has_sponsor")},
                ensure_ascii=False,
            )},
            {"label": "③ 비자 관련 여부", "value": ("예 (" + vis_reason + ")") if resolved["is_visa_related"] else "아니오 → 일반 대화 분기"},
            {"label": "④ 예외 키워드 감지", "value": detected_exception or "감지 안 됨"},
            {"label": "⑤ 키워드 폴백", "value": fallback_note},
            {"label": "⑥ 국가 전환", "value": f"{prev_country}→{new_country} (맥락 초기화)" if country_changed else "없음"},
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
