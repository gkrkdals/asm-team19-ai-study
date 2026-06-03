from functools import lru_cache

from langgraph.graph import StateGraph, END
from agent.state import AgentState
from agent.nodes import (
    intent_classifier,
    visa_rag_search,
    web_search_tool,
    exception_handler,
    response_formatter,
    general_chat,
    search_quality_gate,
    query_refiner,
    knowledge_writer,
)
from agent.routing import route_intent, should_web_search, route_quality
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
    graph.add_node("general_chat", general_chat)
    graph.add_node("visa_rag_search", visa_rag_search)
    graph.add_node("web_search_tool", web_search_tool)
    graph.add_node("search_quality_gate", search_quality_gate)
    graph.add_node("query_refiner", query_refiner)
    graph.add_node("knowledge_writer", knowledge_writer)
    graph.add_node("exception_handler", exception_handler)
    graph.add_node("response_formatter", response_formatter)

    graph.set_entry_point("intent_classifier")

    # 의도 분기: 일반대화 / 예외 / 비자검색 / 재질문
    graph.add_conditional_edges(
        "intent_classifier",
        route_intent,
        {
            "general_chat": "general_chat",
            "visa_rag_search": "visa_rag_search",
            "web_search_tool": "web_search_tool",       # 상세 탐색(딥서치) 직행
            "exception_handler": "exception_handler",
            "response_formatter": "response_formatter",
        },
    )

    # 비자 RAG → (결과 없으면) 웹 검색
    graph.add_conditional_edges(
        "visa_rag_search",
        should_web_search,
        {
            "web_search_tool": "web_search_tool",
            "response_formatter": "response_formatter",
        },
    )

    # 웹 검색 → 신뢰도 게이트 → 분기:
    #   good        → knowledge_writer(ChromaDB 학습 저장) → response_formatter
    #   재시도 한도 → response_formatter (학습 생략)
    #   그 외       → query_refiner(검색어 재생성) → web_search_tool (루프)
    graph.add_edge("web_search_tool", "search_quality_gate")
    graph.add_conditional_edges(
        "search_quality_gate",
        route_quality,
        {
            "query_refiner": "query_refiner",
            "knowledge_writer": "knowledge_writer",
            "response_formatter": "response_formatter",
        },
    )
    graph.add_edge("query_refiner", "web_search_tool")
    graph.add_edge("knowledge_writer", "response_formatter")

    graph.add_edge("general_chat", END)
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
