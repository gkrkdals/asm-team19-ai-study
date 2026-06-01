import logging
from agent.state import AgentState
from agent.config import load_settings

logger = logging.getLogger(__name__)


async def visa_rag_search(state: AgentState) -> dict:
    """ChromaDB에서 관련 비자 정보를 벡터 검색한다."""
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

    if not results:
        return {"search_results": None}

    context = "\n\n".join(
        f"[비자 정보 - {r['metadata'].get('visa_type') or r['metadata'].get('visa_code', '')}]\n{r['document']}"
        for r in results
    )
    return {"search_results": context}


async def web_search_tool(state: AgentState) -> dict:
    """Tavily API로 공식 사이트 실시간 검색을 수행한다."""
    settings = load_settings()
    tavily_key = settings.tavily_api_key or ""
    if not tavily_key or tavily_key.startswith("tvly-..."):
        logger.warning("TAVILY_API_KEY not configured, skipping web search.")
        return {"search_results": None}

    from langchain_community.tools.tavily_search import TavilySearchResults

    country = state.get("country", "")
    purpose = state.get("purpose", "")
    last_msg = state["messages"][-1].content

    country_en = {
        "US": "United States", "JP": "Japan", "GB": "United Kingdom",
        "CA": "Canada", "AU": "Australia", "DE": "Germany",
    }.get(country, country)

    query = f"{country_en} visa {purpose} requirements for Korean citizens 2024 {last_msg}"

    try:
        tool = TavilySearchResults(max_results=4, api_key=tavily_key)
        results = await tool.ainvoke({"query": query})
        context = "\n".join(
            f"[웹 검색] 출처: {r.get('url', '')}\n{r.get('content', '')}"
            for r in (results if isinstance(results, list) else [])
        )
        return {"search_results": context or None}
    except Exception as e:
        logger.error("Web search error: %s", e)
        return {"search_results": None}


async def exception_handler(state: AgentState) -> dict:
    """체류 연장·신분 변경·비자 거절 등 예외 케이스를 처리한다."""
    from rag.vectorstore import search_visas

    exception_type = state.get("exception_type", "general")
    country = state.get("country", "")
    last_msg = state["messages"][-1].content

    exc_query_map = {
        "extension": f"visa stay extension period {country}",
        "status_change": f"visa status change {country}",
        "rejection": f"visa rejection appeal reapplication {country}",
    }
    query = exc_query_map.get(exception_type, last_msg)

    try:
        results = search_visas(query, country_code=country or None, n_results=3)
        context = (
            "\n\n".join(f"[관련 정보]\n{r['document']}" for r in results)
            if results else None
        )
    except Exception as e:
        logger.error("Exception handler RAG error: %s", e)
        context = None

    if not context:
        settings = load_settings()
        tavily_key = settings.tavily_api_key or ""
        if tavily_key and not tavily_key.startswith("tvly-..."):
            try:
                from langchain_community.tools.tavily_search import TavilySearchResults
                tool = TavilySearchResults(max_results=3, api_key=tavily_key)
                web_results = await tool.ainvoke({"query": query})
                context = "\n".join(
                    f"출처: {r.get('url', '')}\n{r.get('content', '')}"
                    for r in (web_results if isinstance(web_results, list) else [])
                )
            except Exception as e:
                logger.error("Exception handler web search error: %s", e)

    return {"search_results": context}
