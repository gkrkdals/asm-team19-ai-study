from agent.state import AgentState


def route_intent(state: AgentState) -> str:
    """intent_classifier 결과에 따라 다음 노드를 결정한다."""
    if not state.get("is_visa_related", True):
        return "general_chat"
    if state.get("is_exception"):
        return "exception_handler"
    if state.get("country") and state.get("purpose"):
        return "visa_rag_search"
    return "response_formatter"


def should_web_search(state: AgentState) -> str:
    """비자 RAG 결과가 없으면 웹 검색으로 분기한다."""
    return "web_search_tool" if not state.get("search_results") else "response_formatter"


def route_quality(state: AgentState) -> str:
    """검색 신뢰도 게이트: 낮으면 검색어 재생성 후 재검색, 충분하면 응답 생성."""
    if state.get("search_quality") == "good":
        return "response_formatter"
    if state.get("search_attempts", 0) >= 2:   # 재시도 한도(초기 1 + 재생성 2)
        return "response_formatter"
    return "query_refiner"
