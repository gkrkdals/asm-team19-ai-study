import logging
from agent.state import AgentState
from agent.config import load_settings

logger = logging.getLogger(__name__)

# 체류 목적 → search_hints 검색어 템플릿 키
PURPOSE_TO_KEYWORD = {
    "employment": "work",
    "study": "student",
    "travel": "tourist",
    "long_stay": "immigration",
    "working_holiday": "work",
}


def _exception_context(query: str, n: int = 2):
    """교차 예외 규칙(쉥겐·환승·ETA 등)을 의미검색해 (context, titles) 반환."""
    try:
        from rag.vectorstore import search_exceptions
        rules = search_exceptions(query, n_results=n)
    except Exception as e:
        logger.error("Exception-rule search error: %s", e)
        return "", []
    if not rules:
        return "", []
    titles = [r["metadata"].get("title", "") for r in rules]
    context = "\n\n".join(
        f"[예외/교차규칙 - {r['metadata'].get('title','')}]\n{r['document']}"
        for r in rules
    )
    return context, titles


async def _tavily_search(country: str, purpose: str, extra: str, tavily_key: str, max_results: int = 4):
    """search_hints 의 우선 도메인·검색어 템플릿으로 Tavily 검색을 수행한다."""
    from knowledge.search_hints import build_tavily_query
    from langchain_community.tools.tavily_search import TavilySearchResults

    hint = build_tavily_query(country or "", PURPOSE_TO_KEYWORD.get(purpose or "", "all"))
    domains = hint.get("include_domains") or []
    query = (hint.get("query") or "").strip()
    if extra:
        query = f"{query} {extra}".strip()

    tool = TavilySearchResults(
        max_results=max_results,
        api_key=tavily_key,
        include_domains=domains,   # 우선 공식 도메인으로 검색 범위 가속/신뢰도 향상
    )
    results = await tool.ainvoke({"query": query})
    rl = results if isinstance(results, list) else []
    urls = [r.get("url", "") for r in rl if r.get("url")]
    context = "\n".join(
        f"[웹 검색] 출처: {r.get('url', '')}\n{r.get('content', '')}" for r in rl
    )
    return {"query": query, "domains": domains, "urls": urls, "context": context, "count": len(rl)}


async def visa_rag_search(state: AgentState) -> dict:
    """ChromaDB에서 관련 비자 정보 + 교차 예외 규칙을 벡터 검색한다."""
    from rag.vectorstore import search_visas

    country = state.get("country", "")
    purpose = state.get("purpose", "")
    last_msg = state["messages"][-1].content

    query = f"Country:{country} Purpose:{purpose}"
    if state.get("duration"):
        query += f" Duration:{state['duration']}"
    if state.get("profession"):
        query += f" Profession:{state['profession']}"
    query += f" | {last_msg}"

    try:
        results = search_visas(query, country_code=country, n_results=5)
    except Exception as e:
        logger.error("RAG search error: %s", e)
        results = []

    # 교차 예외 규칙(쉥겐·환승·유효기간≠체류 등)도 함께 검색해 컨텍스트에 병합
    exc_context, exc_titles = _exception_context(last_msg or query, n=2)

    matched = [
        (r["metadata"].get("visa_type") or r["metadata"].get("visa_code") or "?")
        for r in results
    ]

    parts = []
    if results:
        parts.append("\n\n".join(
            f"[비자 정보 - {r['metadata'].get('visa_type') or r['metadata'].get('visa_code', '')}]\n{r['document']}"
            for r in results
        ))
    if exc_context:
        parts.append(exc_context)
    combined = "\n\n".join(parts) if parts else None

    detail = {
        "node": "visa_rag_search",
        "headline": "ChromaDB 벡터 검색(코사인 유사도) + 교차 예외규칙",
        "items": [
            {"label": "① RAG 질의어(query)", "value": query},
            {"label": "② 국가 필터(country_code)", "value": country or "전체"},
            {"label": "③ 비자 결과 수", "value": f"{len(results)}건"},
            {"label": "④ 매칭 비자", "value": ", ".join(matched) if matched else "없음"},
            {"label": "⑤ 교차규칙(예외) 병합", "value": (
                f"{len(exc_titles)}건: " + ", ".join(t for t in exc_titles if t)
                if exc_titles else "0건")},
            {"label": "→ 다음 분기 근거", "value": (
                "컨텍스트 확보 → response_formatter 로 이동"
                if combined else "결과 0건 → web_search_tool(Tavily 폴백)로 이동"
            )},
        ],
    }

    return {"search_results": combined, "node_details": [detail]}


async def web_search_tool(state: AgentState) -> dict:
    """Tavily API로 공식 사이트 실시간 검색(우선 도메인·검색어 템플릿 적용)."""
    settings = load_settings()
    tavily_key = settings.tavily_api_key or ""

    country = state.get("country", "")
    purpose = state.get("purpose", "")
    last_msg = state["messages"][-1].content

    if not tavily_key or tavily_key.startswith("tvly-..."):
        logger.warning("TAVILY_API_KEY not configured, skipping web search.")
        from knowledge.search_hints import build_tavily_query
        hint = build_tavily_query(country or "", PURPOSE_TO_KEYWORD.get(purpose or "", "all"))
        detail = {
            "node": "web_search_tool",
            "headline": "Tavily 웹 검색 (미설정)",
            "items": [
                {"label": "① 예상 검색어", "value": hint.get("query", "")},
                {"label": "② 우선 도메인", "value": ", ".join(hint.get("include_domains") or []) or "없음(일반 검색)"},
                {"label": "③ 상태", "value": "TAVILY_API_KEY 미설정 → 웹검색 건너뜀"},
            ],
        }
        return {"search_results": None, "node_details": [detail]}

    try:
        res = await _tavily_search(country, purpose, last_msg, tavily_key, max_results=4)
        detail = {
            "node": "web_search_tool",
            "headline": "Tavily 웹 검색 실행 (우선 도메인 적용)",
            "items": [
                {"label": "① 검색어(query)", "value": res["query"]},
                {"label": "② 우선 도메인(include_domains)", "value": ", ".join(res["domains"]) or "없음(일반 검색)"},
                {"label": "③ 결과 수", "value": f"{res['count']}건"},
                {"label": "④ 출처 URL", "value": "\n".join(res["urls"]) if res["urls"] else "없음"},
                {"label": "⑤ 컨텍스트 길이", "value": f"{len(res['context']):,}자"},
            ],
        }
        return {"search_results": res["context"] or None, "node_details": [detail]}
    except Exception as e:
        logger.error("Web search error: %s", e)
        detail = {
            "node": "web_search_tool",
            "headline": "Tavily 웹 검색 오류",
            "items": [{"label": "오류", "value": str(e)[:300]}],
        }
        return {"search_results": None, "node_details": [detail]}


async def exception_handler(state: AgentState) -> dict:
    """체류 연장·신분 변경·거절 + 쉥겐·환승 등 교차 예외 케이스를 처리한다."""
    from rag.vectorstore import search_visas

    exception_type = state.get("exception_type", "general")
    country = state.get("country", "")
    purpose = state.get("purpose", "")
    last_msg = state["messages"][-1].content

    exc_query_map = {
        "extension": f"visa stay extension period {country}",
        "status_change": f"visa status change {country}",
        "rejection": f"visa rejection appeal reapplication {country}",
    }
    query = exc_query_map.get(exception_type, last_msg)

    items = [
        {"label": "① 예외 유형", "value": exception_type or "general"},
        {"label": "② 질의어", "value": query},
        {"label": "③ 국가 필터", "value": country or "전체"},
    ]

    # 1) 교차 예외 규칙 우선 병합
    exc_context, exc_titles = _exception_context(last_msg or query, n=3)
    items.append({"label": "④ 교차규칙(예외) 매칭", "value": (
        f"{len(exc_titles)}건: " + ", ".join(t for t in exc_titles if t) if exc_titles else "0건")})

    # 2) 비자 문서 RAG
    try:
        results = search_visas(query, country_code=country or None, n_results=3)
        visa_context = "\n\n".join(f"[관련 정보]\n{r['document']}" for r in results) if results else ""
        items.append({"label": "⑤ 비자 RAG 결과 수", "value": f"{len(results)}건"})
    except Exception as e:
        logger.error("Exception handler RAG error: %s", e)
        visa_context = ""
        items.append({"label": "⑤ 비자 RAG 결과 수", "value": f"오류: {str(e)[:120]}"})

    parts = [c for c in (exc_context, visa_context) if c]
    context = "\n\n".join(parts) if parts else None

    # 3) 여전히 비면 Tavily 폴백(우선 도메인 적용)
    if not context:
        settings = load_settings()
        tavily_key = settings.tavily_api_key or ""
        if tavily_key and not tavily_key.startswith("tvly-..."):
            try:
                res = await _tavily_search(country, purpose, query, tavily_key, max_results=3)
                context = res["context"] or None
                items.append({"label": "⑥ RAG 0건 → Tavily 폴백", "value": (
                    f"{res['count']}건 · 도메인 {', '.join(res['domains']) or '일반'}")})
            except Exception as e:
                logger.error("Exception handler web search error: %s", e)
                items.append({"label": "⑥ Tavily 폴백 오류", "value": str(e)[:120]})

    detail = {
        "node": "exception_handler",
        "headline": "예외 전용: 교차규칙 + 비자RAG" + (" + 웹폴백" if not parts else ""),
        "items": items,
    }
    return {"search_results": context, "node_details": [detail]}
