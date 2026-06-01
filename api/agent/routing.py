from agent.state import AgentState


def route_intent(state: AgentState) -> str:
    """intent_classifier 결과에 따라 다음 노드를 결정한다."""
    if state.get("is_exception"):
        return "exception_handler"
    if state.get("country") and state.get("purpose"):
        return "visa_rag_search"
    return "response_formatter"


def should_web_search(state: AgentState) -> str:
    """RAG 결과가 없으면 웹 검색으로 분기한다."""
    return "web_search_tool" if not state.get("search_results") else "response_formatter"
