import logging
from langchain_core.messages import SystemMessage, HumanMessage
from agent.state import AgentState
from agent.domain import COUNTRY_KO, PURPOSE_KO, EXCEPTION_KO, SYSTEM_PROMPT
from agent.nodes.llm import get_llm

logger = logging.getLogger(__name__)


async def response_formatter(state: AgentState) -> dict:
    """검색 결과와 대화 컨텍스트를 바탕으로 최종 응답을 생성한다."""
    llm = get_llm()

    country = state.get("country")
    purpose = state.get("purpose")
    is_exception = state.get("is_exception", False)
    exception_type = state.get("exception_type")
    search_results = state.get("search_results")
    extra_context = state.get("extra_context")
    last_msg = state["messages"][-1].content

    if not country and not purpose and not is_exception:
        try:
            response = await llm.ainvoke(
                [SystemMessage(content=SYSTEM_PROMPT)] + list(state["messages"])
            )
            return {"final_response": response.content}
        except Exception as e:
            logger.error("LLM clarification error: %s", e)
            return {"final_response": (
                "안녕하세요! 어느 **나라**에서, **얼마나**, **무슨 목적**(취업/유학/여행/장기체류)으로 "
                "체류하실 계획인지 알려주시면 적합한 비자 정보를 안내드리겠습니다.\n\n"
                "지원 국가: 🇺🇸 미국 · 🇯🇵 일본 · 🇬🇧 영국 · 🇨🇦 캐나다 · 🇦🇺 호주 · 🇩🇪 독일"
            )}

    if is_exception:
        task = f"{EXCEPTION_KO.get(exception_type, '예외 상황')} 상황에 대해 안내해주세요."
    else:
        country_label = COUNTRY_KO.get(country, country)
        purpose_label = PURPOSE_KO.get(purpose, purpose)
        task = f"{country_label} {purpose_label} 비자에 대해 안내해주세요."

    context_parts = []
    if search_results:
        context_parts.append(search_results)
    if extra_context:
        context_parts.append("[교차 예외규칙 — 반드시 검토]\n" + extra_context)
    context_section = ("\n\n참고 정보:\n" + "\n\n".join(context_parts)) if context_parts else ""

    # ── 후속/상세 질문 압축 응답 ──────────────────────────────────────────
    # 이전 대화에서 이미 같은 비자(국가+목적)를 안내했고, 지금은 그에 대한
    # 추가·상세 질문(필요서류/대체조건/처리기간 등)인 경우:
    #   전체 추천 템플릿을 반복하지 않고, 물어본 것만 간결히 답하며 상위 대화를 참조한다.
    is_followup = state.get("is_followup", False)
    if is_followup:
        _clabel = COUNTRY_KO.get(country, country) if country else ""
        _plabel = PURPOSE_KO.get(purpose, purpose) if purpose else ""
        _ref = (f"{_clabel} {_plabel} 비자".strip()) or "앞서 안내드린 비자"
        fu_prompt = f"""사용자는 앞선 대화에서 '{_ref}'에 대한 안내를 이미 받았고, 지금은 그에 대한 **후속·상세 질문**을 했습니다.

[가장 중요] 이전 대화에서 이미 제공한 '추천 비자·전체 자격요건·서류 목록'을 처음부터 다시 나열하지 마세요.
지금 사용자가 **새로 물은 부분에만** 간결하게 답하세요.

사용자의 후속 질문: {last_msg}{context_section}

작성 규칙:
1) '## 추천 비자', '## 주요 자격 요건' 같은 전체 안내 템플릿을 반복하지 마세요.
2) 질문에 직접 답하는 핵심 내용만 쓰세요(필요하면 짧은 목록이나 소제목 1개 정도만 허용).
3) 첫 문장에서 앞선 안내와 이어진다는 점을 가볍게 언급하세요. 예: "앞서 안내드린 {_ref} 기준으로 말씀드리면,".
4) 참고 정보에 근거가 있으면 그 내용을 우선 사용하고, 없으면 일반적으로 알려진 사실만 간단히 답하세요. URL은 참고 정보에 있는 것만 인용하세요.
5) 마지막 줄에 한 줄 면책만 덧붙이세요: "⚠️ 참고용 안내이며, 신청 전 공식 기관에서 최신 요건을 확인해 주세요."
"""
        fu_messages = (
            [SystemMessage(content=SYSTEM_PROMPT)]
            + list(state["messages"][:-1][-6:])   # 이전 대화(특히 직전 전체 안내) 포함 → 상위 대화 참조
            + [HumanMessage(content=fu_prompt)]
        )
        try:
            response = await llm.ainvoke(fu_messages)
            detail = {
                "node": "response_formatter",
                "headline": "후속질문 압축 응답 — 전체 템플릿 생략, 필요한 답만",
                "items": [
                    {"label": "① 응답 모드", "value": "is_followup=True → 압축(상위 대화 참조)"},
                    {"label": "② 참조 대상", "value": _ref},
                    {"label": "③ 후속 질문", "value": last_msg},
                    {"label": "④ 처리", "value": "추천/요건/서류 재출력 생략, 물어본 부분만 답변"},
                ],
            }
            return {"final_response": response.content, "node_details": [detail]}
        except Exception as e:
            logger.error("Followup compression failed, fallback to full template: %s", e)
            # 실패 시 아래 표준 템플릿 경로로 폴백(return 하지 않음)

    # 처리 기간·수수료 섹션: 검색 결과에 관련 데이터가 있을 때만 포함
    fee_keywords = ["수수료", "fee", "처리 기간", "processing time", "weeks", "days", "CAD", "USD", "EUR", "AUD", "GBP"]
    has_fee_info = search_results and any(kw.lower() in search_results.lower() for kw in fee_keywords)
    fee_section = (
        "\n\n## 처리 기간 및 수수료\n(참고 자료에 명시된 수치만 기재)"
        if has_fee_info else ""
    )

    # URL 정책: 검색 결과에 실제 등장한 URL만 인용 — 모델이 URL을 생성하면 DNS 오류(NXDOMAIN) 발생
    if search_results and ("http://" in search_results or "https://" in search_results):
        url_section = "\n\n## 공식 참고 링크\n(위 참고 자료에 포함된 URL만 그대로 인용. 없으면 이 섹션 생략)"
    else:
        url_section = ""  # URL 정보 없으면 섹션 자체를 제거

    prompt = f"""{task}

사용자 질문: {last_msg}{context_section}

다음 형식으로 친절하고 명확하게 한국어로 답변하세요:

## 추천 비자
(비자 종류 및 간략 설명)

## 주요 자격 요건
(핵심 요건 목록)

## 필요 서류
(주요 서류 목록){fee_section}

## 주의사항
(놓치기 쉬운 사항){url_section}

---
⚠️ 이 정보는 참고용이며, 실제 신청 시 해당 국가 공식 기관(대사관·이민국)에서 최신 정보를 확인하세요.

[URL 규칙] URL은 위 참고 자료에 실제로 포함된 것만 사용하세요. 추측하거나 만들어내지 마세요."""

    history = list(state["messages"][:-1][-6:])
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + history + [HumanMessage(content=prompt)]

    try:
        response = await llm.ainvoke(messages)
        return {"final_response": response.content}
    except Exception as e:
        logger.error("Response generation error: %s", e)
        return {"final_response": "죄송합니다. 현재 응답을 생성하지 못했습니다. 잠시 후 다시 시도해 주세요."}
