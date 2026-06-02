from functools import lru_cache

from langgraph.graph import StateGraph, END
from agent.state import AgentState
from agent.nodes import (
    intent_classifier,
    visa_rag_search,
    web_search_tool,
    exception_handler,
    response_formatter,
)
from agent.routing import route_intent, should_web_search
from agent.config import load_settings, validate_settings


def build_graph():
    """
    LangGraph Agentic Workflow:

    intent_classifier
         ↓ (conditional)
    ┌────────────────────┬─────────────────────┐
    visa_rag_search  exception_handler  response_formatter
         ↓ (conditional)       ↓               ↓
    ┌──────────────┐           │               │
    web_search_tool            │               │
         └──────────────────── ↓ ──────────────┘
                        response_formatter
                               ↓
                              END
    """
    graph = StateGraph(AgentState)
    validate_settings(load_settings())

    graph.add_node("intent_classifier", intent_classifier)
    graph.add_node("visa_rag_search", visa_rag_search)
    graph.add_node("web_search_tool", web_search_tool)
    graph.add_node("exception_handler", exception_handler)
    graph.add_node("response_formatter", response_formatter)

    graph.set_entry_point("intent_classifier")

    graph.add_conditional_edges(
        "intent_classifier",
        route_intent,
        {
            "visa_rag_search": "visa_rag_search",
            "exception_handler": "exception_handler",
            "response_formatter": "response_formatter",
        },
    )

    graph.add_conditional_edges(
        "visa_rag_search",
        should_web_search,
        {
            "web_search_tool": "web_search_tool",
            "response_formatter": "response_formatter",
        },
    )

    graph.add_edge("web_search_tool", "response_formatter")
    graph.add_edge("exception_handler", "response_formatter")
    graph.add_edge("response_formatter", END)

    return graph.compile()


@lru_cache(maxsize=1)
def get_graph():
    """컴파일된 그래프 싱글턴.

    채팅 라우터와 워크플로우 트레이스 라우터가 동일한 컴파일 인스턴스를
    공유하도록 보장한다(토폴로지와 실제 실행이 항상 일치).
    """
    return build_graph()
