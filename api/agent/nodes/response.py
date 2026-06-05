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
