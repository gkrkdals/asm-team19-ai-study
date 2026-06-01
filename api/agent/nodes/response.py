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

    context_section = f"\n\n참고 정보:\n{search_results}" if search_results else ""

    prompt = f"""{task}

사용자 질문: {last_msg}{context_section}

다음 형식으로 친절하고 명확하게 한국어로 답변하세요:

## 추천 비자
(비자 종류 및 간략 설명)

## 주요 자격 요건
(핵심 요건 목록)

## 필요 서류
(주요 서류 목록)

## 처리 기간 및 수수료
(알 경우 명시, 모를 경우 '공식 사이트 확인 필요' 표기)

## 주의사항
(놓치기 쉬운 사항)

## 공식 참고 링크
(관련 공식 URL)

---
⚠️ 이 정보는 참고용이며, 실제 신청 시 해당 국가 공식 기관(대사관·이민국)에서 최신 정보를 확인하세요."""

    history = list(state["messages"][:-1][-6:])
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + history + [HumanMessage(content=prompt)]

    try:
        response = await llm.ainvoke(messages)
        return {"final_response": response.content}
    except Exception as e:
        logger.error("Response generation error: %s", e)
        return {"final_response": "죄송합니다. 현재 응답을 생성하지 못했습니다. 잠시 후 다시 시도해 주세요."}
