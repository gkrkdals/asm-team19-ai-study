"""
검색 신뢰도 게이트 + LLM 기반 검색어 재생성.

웹 검색(Tavily) 결과가 공식 출처를 충분히 포함하지 못하면, LLM이 한국어 질문을
영어 공식 검색어로 다시 생성(다양한 키워드·동의어)하여 재검색하도록 루프를 만든다.
리뷰 피드백("신뢰도 낮은 출처면 검색어를 재생성해 다시 검색", "LLM이 검색어 생성",
"한국어→영어 변환") 반영.
"""
import logging
from langchain_core.messages import HumanMessage
from agent.state import AgentState
from agent.nodes.llm import get_llm

logger = logging.getLogger(__name__)

_MIN_CONTEXT_LEN = 400


async def search_quality_gate(state: AgentState) -> dict:
    """웹 검색 결과의 신뢰도(공식 도메인 포함·내용 충분성)를 평가한다."""
    from knowledge.search_hints import get_priority_domains

    country = state.get("country", "") or ""
    ctx = state.get("search_results") or ""
    attempts = state.get("search_attempts", 0)
    domains = get_priority_domains(country)

    has_official = any(d in ctx for d in domains) if domains else False
    enough = len(ctx) >= _MIN_CONTEXT_LEN

    if domains:
        quality = "good" if (has_official and enough) else "poor"
        basis = f"공식도메인({', '.join(domains)}) 포함={has_official}, 내용량 {len(ctx)}자"
    else:
        quality = "good" if enough else "poor"
        basis = f"우선도메인 미등록 국가 → 내용량 {len(ctx)}자 기준"

    nxt = ("신뢰도 충분 → response_formatter"
           if quality == "good" or attempts >= 2
           else "신뢰도 낮음 → query_refiner(검색어 재생성) 후 재검색")

    detail = {
        "node": "search_quality_gate",
        "headline": "검색 결과 신뢰도 평가",
        "items": [
            {"label": "① 평가 기준", "value": basis},
            {"label": "② 판정", "value": quality},
            {"label": "③ 재검색 횟수", "value": f"{attempts}/2"},
            {"label": "→ 다음", "value": nxt},
        ],
    }
    return {"search_quality": quality, "node_details": [detail]}


async def query_refiner(state: AgentState) -> dict:
    """LLM으로 더 나은 영어 공식 검색어를 생성한다(한국어→영어, 다양한 키워드)."""
    llm = get_llm()
    country = state.get("country", "") or ""
    purpose = state.get("purpose", "") or ""
    last_msg = state["messages"][-1].content
    prev_query = state.get("web_query", "") or ""
    attempts = state.get("search_attempts", 0)

    from knowledge.search_hints import COUNTRY_NAMES, get_priority_domains
    country_en = COUNTRY_NAMES.get(country, country)
    domains = get_priority_domains(country)

    prompt = f"""너는 해외 비자 정보를 공식 출처에서 찾기 위한 '웹 검색어'를 만드는 도우미다.

국가: {country_en} ({country})
체류 목적: {purpose or '미상'}
직전 검색어(결과 부실): "{prev_query}"
참고 공식 도메인: {', '.join(domains) if domains else '없음'}

규칙:
- 영어로만, 핵심 키워드 위주: 국가명/국가코드 + visa + (work/student/tourist 등 목적) + requirements/eligibility/official/immigration.
- 'Korea', 'Korean', 'South Korea', 'for Korean citizens' 같은 한국 관련 단어는 절대 포함하지 마라(출처 매칭 저하).
- 직전 검색어와 다른 동의어/표현을 사용한다.
- 한 줄로 검색어만 출력한다(따옴표·설명·한국어 금지)."""

    try:
        resp = await llm.ainvoke([HumanMessage(content=prompt)])
        new_query = (resp.content or "").strip().splitlines()[0].strip().strip('"')
    except Exception as e:  # noqa: BLE001
        logger.error("query_refiner error: %s", e)
        new_query = f"{country_en} {purpose} visa official requirements immigration"

    detail = {
        "node": "query_refiner",
        "headline": "LLM 검색어 재생성 (한국어→영어·다양 키워드)",
        "items": [
            {"label": "① 직전 검색어", "value": prev_query or "(초기)"},
            {"label": "② 재생성 검색어", "value": new_query},
            {"label": "③ 재시도", "value": f"{attempts + 1}회차"},
            {"label": "→ 다음", "value": "web_search_tool 로 재검색"},
        ],
    }
    return {"web_query": new_query, "search_attempts": attempts + 1, "node_details": [detail]}
