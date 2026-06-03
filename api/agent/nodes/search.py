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


def _exception_context(query: str, last_msg: str = "", n: int = 3):
    """교차 예외 규칙을 하이브리드(키워드 + 의미검색)로 찾아 (context, titles) 반환.

    한국어 임베딩 한계로 의미검색만으로는 쉥겐·환승 규칙이 누락되기 쉬우므로,
    규칙에 정의된 keywords 가 사용자 메시지에 직접 등장하면 우선 포함한다.
    """
    msg = (last_msg or "").lower()
    picked: list = []           # (title, text) 튜플, 순서 유지
    seen: set = set()

    # 1) 키워드 직접 매칭(정확도 높음)
    try:
        from knowledge.exceptions import all_rules
        for r in all_rules():
            if any(k.lower() in msg for k in r.keywords):
                if r.id not in seen:
                    seen.add(r.id)
                    picked.append((r.title, r.to_rag_chunk()["text"]))
    except Exception as e:
        logger.error("Exception keyword match error: %s", e)

    # 2) 의미검색으로 보강
    try:
        from rag.vectorstore import search_exceptions
        for r in search_exceptions(query, n_results=n):
            rid = r["metadata"].get("rule_id", "")
            if rid and rid not in seen:
                seen.add(rid)
                picked.append((r["metadata"].get("title", ""), r["document"]))
    except Exception as e:
        logger.error("Exception-rule search error: %s", e)

    if not picked:
        return "", []
    picked = picked[:max(n, len(picked) if msg else n)][:4]   # 과다 방지(최대 4건)
    titles = [t for t, _ in picked]
    context = "\n\n".join(f"[예외/교차규칙 - {t}]\n{txt}" for t, txt in picked)
    return context, titles


async def _run_tavily(query: str, domains: list, tavily_key: str, max_results: int = 4, deep: bool = False):
    """Tavily 저수준 실행기. (우선)도메인 제한 적용.

    deep=True 면 search_depth='advanced' + include_raw_content 로 공식 사이트 원문까지
    상세 탐색한다(후속 '공식 사이트 상세 탐색' 기능).
    """
    from langchain_community.tools.tavily_search import TavilySearchResults
    kwargs = dict(max_results=max_results, api_key=tavily_key, include_domains=domains or [])
    if deep:
        kwargs.update(search_depth="advanced", include_raw_content=True)
    tool = TavilySearchResults(**kwargs)
    results = await tool.ainvoke({"query": query})
    rl = results if isinstance(results, list) else []
    urls = [r.get("url", "") for r in rl if r.get("url")]

    def _body(r: dict) -> str:
        if deep and r.get("raw_content"):
            return (r.get("raw_content") or "")[:1800]   # 원문 일부(과다 방지)
        return r.get("content", "")

    context = "\n".join(
        f"[웹 검색] 출처: {r.get('url', '')}\n{_body(r)}" for r in rl
    )
    return {"urls": urls, "context": context, "count": len(rl)}


async def visa_rag_search(state: AgentState) -> dict:
    """ChromaDB 비자 문서를 검색하고, 교차 예외 규칙은 보조 컨텍스트로 분리 제공한다."""
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

    # 교차 예외 규칙은 라우팅(웹폴백 여부)에 영향을 주지 않도록 extra_context 로 분리
    exc_context, exc_titles = _exception_context(last_msg or query, last_msg=last_msg, n=2)

    matched = [(r["metadata"].get("visa_type") or r["metadata"].get("visa_code") or "?") for r in results]
    visa_context = "\n\n".join(
        f"[비자 정보 - {r['metadata'].get('visa_type') or r['metadata'].get('visa_code', '')}]\n{r['document']}"
        for r in results
    ) if results else None

    detail = {
        "node": "visa_rag_search",
        "headline": "ChromaDB 벡터 검색(코사인 유사도) + 교차 예외규칙",
        "items": [
            {"label": "① RAG 질의어(query)", "value": query},
            {"label": "② 국가 필터(country_code)", "value": country or "전체"},
            {"label": "③ 비자 결과 수", "value": f"{len(results)}건"},
            {"label": "④ 매칭 비자", "value": ", ".join(matched) if matched else "없음"},
            {"label": "⑤ 교차규칙(예외) 병합", "value": (
                f"{len(exc_titles)}건: " + ", ".join(t for t in exc_titles if t) if exc_titles else "0건")},
            {"label": "→ 다음 분기 근거", "value": (
                "비자 결과 있음 → response_formatter"
                if visa_context else "비자 결과 0건 → web_search_tool(Tavily 폴백)")},
        ],
    }
    return {"search_results": visa_context, "extra_context": exc_context or None, "node_details": [detail]}


async def web_search_tool(state: AgentState) -> dict:
    """Tavily 웹 검색(우선 도메인 + 재생성 검색어 지원)."""
    from knowledge.search_hints import build_tavily_query, get_priority_domains

    settings = load_settings()
    tavily_key = settings.tavily_api_key or ""
    country = state.get("country", "")
    purpose = state.get("purpose", "")
    deep = bool(state.get("deep_search"))
    last_msg = state["messages"][-1].content

    # 검색어는 '국가명 + visa + requirements …' 형태의 영어 핵심 쿼리만 사용한다.
    # (한국어 원문/Korea 관련 단어를 배제해 공식 출처 매칭률을 높임)
    refined = state.get("web_query")
    hint = build_tavily_query(country or "", PURPOSE_TO_KEYWORD.get(purpose or "", "all"))
    domains = get_priority_domains(country)
    query = refined or hint["query"]
    max_results = 6 if deep else 4

    if not tavily_key or tavily_key.startswith("tvly-..."):
        logger.warning("TAVILY_API_KEY not configured, skipping web search.")
        detail = {
            "node": "web_search_tool",
            "headline": "Tavily 웹 검색 (미설정)",
            "items": [
                {"label": "① 검색어", "value": query},
                {"label": "② 우선 도메인", "value": ", ".join(domains) or "없음(일반 검색)"},
                {"label": "③ 상태", "value": "TAVILY_API_KEY 미설정 → 웹검색 건너뜀"},
            ],
        }
        return {"search_results": None, "web_query": query, "node_details": [detail]}

    try:
        res = await _run_tavily(query, domains, tavily_key, max_results=max_results, deep=deep)
        mode = "공식 사이트 상세 탐색(advanced+원문)" if deep else (
            "재생성 검색어" if refined else "우선 도메인")
        detail = {
            "node": "web_search_tool",
            "headline": "Tavily 웹 검색 실행 — " + mode,
            "items": [
                {"label": "① 검색어(query)", "value": query},
                {"label": "② 우선 도메인(include_domains)", "value": ", ".join(domains) or "없음(일반 검색)"},
                {"label": "③ 검색 깊이", "value": "advanced(원문 포함)" if deep else "basic"},
                {"label": "④ 결과 수", "value": f"{res['count']}건"},
                {"label": "⑤ 출처 URL", "value": "\n".join(res["urls"]) if res["urls"] else "없음"},
                {"label": "⑥ 컨텍스트 길이", "value": f"{len(res['context']):,}자"},
            ],
        }
        return {"search_results": res["context"] or None, "web_query": query, "node_details": [detail]}
    except Exception as e:
        logger.error("Web search error: %s", e)
        detail = {
            "node": "web_search_tool",
            "headline": "Tavily 웹 검색 오류",
            "items": [{"label": "오류", "value": str(e)[:300]}],
        }
        return {"search_results": None, "web_query": query, "node_details": [detail]}


async def exception_handler(state: AgentState) -> dict:
    """체류 연장·변경·거절 + 쉥겐·환승 등 교차 예외 케이스를 처리한다."""
    from rag.vectorstore import search_visas
    from knowledge.search_hints import get_priority_domains

    exception_type = state.get("exception_type", "general")
    country = state.get("country", "")
    last_msg = state["messages"][-1].content

    exc_query_map = {
        "extension": f"visa stay extension I-539 period {country}",
        "status_change": f"visa status change tourist to work {country}",
        "rejection": f"visa rejection appeal reapplication {country}",
        "emergency": f"emergency expedited visa premium processing appointment {country}",
    }
    query = exc_query_map.get(exception_type, last_msg)

    items = [
        {"label": "① 예외 유형", "value": exception_type or "general"},
        {"label": "② 질의어", "value": query},
        {"label": "③ 국가 필터", "value": country or "전체"},
    ]

    # 1) 교차 예외 규칙(핵심)
    exc_context, exc_titles = _exception_context(last_msg or query, last_msg=last_msg, n=3)
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

    primary = visa_context or None

    # 3) 비자 RAG·예외 둘 다 비면 Tavily 폴백(우선 도메인)
    if not primary and not exc_context:
        settings = load_settings()
        tavily_key = settings.tavily_api_key or ""
        if tavily_key and not tavily_key.startswith("tvly-..."):
            try:
                domains = get_priority_domains(country)
                res = await _run_tavily(query, domains, tavily_key, max_results=3)
                primary = res["context"] or None
                items.append({"label": "⑥ RAG 0건 → Tavily 폴백", "value": (
                    f"{res['count']}건 · 도메인 {', '.join(domains) or '일반'}")})
            except Exception as e:
                logger.error("Exception handler web search error: %s", e)
                items.append({"label": "⑥ Tavily 폴백 오류", "value": str(e)[:120]})

    detail = {
        "node": "exception_handler",
        "headline": "예외 전용: 교차규칙 + 비자RAG",
        "items": items,
    }
    return {"search_results": primary, "extra_context": exc_context or None, "node_details": [detail]}
