"""
워크플로우 트레이스용 노드 메타데이터.

확장 지점(Single Extension Point)
────────────────────────────────────────────────────────────
LangGraph 노드를 새로 추가했을 때, 트레이스 화면에 한글 라벨/설명/데이터
출처를 보여주고 싶다면 아래 ``NODE_META`` 딕셔너리에 한 줄만 추가하면 된다.
추가하지 않아도 ``describe_node`` 의 폴백이 동작하므로 트레이스 자체는 깨지지
않는다. 즉 그래프(graph.py)만 고치면 /trace URL 은 자동으로 새 노드를 그린다.
"""
from __future__ import annotations

from typing import Any

# ── 데이터 출처(plain data 가 어디서 참조되는지) 라벨 ─────────────────────
SOURCE_LABELS: dict[str, str] = {
    "LLM": "LLM 추론",
    "VectorDB": "벡터DB(ChromaDB)",
    "WebSearch": "웹검색(Tavily)",
    "Rule": "규칙 기반",
    "State": "대화 상태(State)",
}

# ── 노드별 표시 메타데이터 ────────────────────────────────────────────────
# label   : 화면에 표시할 한글 이름
# icon    : 이모지 아이콘
# desc    : 노드가 하는 일(자연어 설명)
# sources : 이 노드가 참조하는 plain data 출처 (SOURCE_LABELS 키)
# produces: 이 노드가 State 에 기록(정제)하는 필드들
NODE_META: dict[str, dict[str, Any]] = {
    "intent_classifier": {
        "label": "의도 분석",
        "icon": "🧭",
        "desc": "사용자 자연어에서 국가·목적·기간·직업을 추출하고 예외 키워드를 감지합니다.",
        "sources": ["LLM", "Rule", "State"],
        "produces": ["country", "purpose", "duration", "profession", "is_exception", "exception_type"],
    },
    "visa_rag_search": {
        "label": "비자 RAG 검색",
        "icon": "📚",
        "desc": "ChromaDB 벡터 검색으로 (국가·목적) 조건에 맞는 비자 문서를 조회합니다.",
        "sources": ["VectorDB"],
        "produces": ["search_results"],
    },
    "web_search_tool": {
        "label": "웹 검색 (Tavily)",
        "icon": "🌐",
        "desc": "RAG 결과가 비어 있을 때 Tavily 로 공식 사이트를 실시간 검색합니다.",
        "sources": ["WebSearch"],
        "produces": ["search_results"],
    },
    "exception_handler": {
        "label": "예외 처리",
        "icon": "⚠️",
        "desc": "체류 연장·신분 변경·비자 거절 등 예외 상황 전용으로 검색합니다.",
        "sources": ["VectorDB", "WebSearch"],
        "produces": ["search_results"],
    },
    "response_formatter": {
        "label": "응답 생성",
        "icon": "✍️",
        "desc": "검색 컨텍스트와 대화 맥락을 LLM 으로 종합해 최종 답변을 작성합니다.",
        "sources": ["LLM", "State"],
        "produces": ["final_response"],
    },
    "general_chat": {
        "label": "일반 대화",
        "icon": "💬",
        "desc": "비자와 무관한 질문을 간단히 응대하고 비자 도메인으로 유도합니다.",
        "sources": ["LLM"],
        "produces": ["final_response"],
    },
    "search_quality_gate": {
        "label": "검색 신뢰도 게이트",
        "icon": "🔎",
        "desc": "웹 검색 결과의 공식 출처 포함·내용 충분성을 평가해 재검색 여부를 결정합니다.",
        "sources": ["Rule"],
        "produces": ["search_quality"],
    },
    "query_refiner": {
        "label": "검색어 재생성",
        "icon": "🔁",
        "desc": "신뢰도가 낮으면 LLM 이 한국어→영어 공식 검색어를 다시 생성해 재검색합니다.",
        "sources": ["LLM"],
        "produces": ["web_query", "search_attempts"],
    },
}

# 그래프의 가상 시작/끝 노드
TERMINAL_NODES = {
    "__start__": {"label": "시작", "icon": "▶️"},
    "__end__": {"label": "종료", "icon": "🏁"},
}

# ── 간선(엣지) 라벨: 어떤 조건/데이터로 이 간선을 타는지 ────────────────────
# 새 간선을 의미 있게 표기하려면 (source, target) 키를 추가한다. 없으면 라벨 생략.
EDGE_LABELS: dict[tuple[str, str], str] = {
    ("intent_classifier", "general_chat"): "비자 무관 질문",
    ("intent_classifier", "visa_rag_search"): "국가·목적 확인됨",
    ("intent_classifier", "exception_handler"): "예외 키워드 감지",
    ("intent_classifier", "response_formatter"): "정보 부족 → 재질문",
    ("visa_rag_search", "web_search_tool"): "비자 결과 0건",
    ("visa_rag_search", "response_formatter"): "비자 결과 있음",
    ("web_search_tool", "search_quality_gate"): "검색 결과 평가",
    ("search_quality_gate", "query_refiner"): "신뢰도 낮음",
    ("search_quality_gate", "response_formatter"): "신뢰도 충분",
    ("query_refiner", "web_search_tool"): "재생성 검색어로 재검색",
    ("web_search_tool", "response_formatter"): "웹 검색 결과 반영",
    ("exception_handler", "response_formatter"): "예외 정보 반영",
}


def edge_label(source: str, target: str) -> str:
    return EDGE_LABELS.get((source, target), "")

# State 필드 한글 라벨
FIELD_KO: dict[str, str] = {
    "country": "국가",
    "purpose": "목적",
    "duration": "기간",
    "profession": "직업/분야",
    "has_sponsor": "스폰서 여부",
    "is_exception": "예외 여부",
    "exception_type": "예외 유형",
    "search_results": "검색 컨텍스트",
    "final_response": "최종 답변",
}

_MAX_PREVIEW = 1400


def describe_node(name: str) -> dict[str, Any]:
    """노드 이름으로 표시 메타데이터를 돌려준다. 미등록 노드는 폴백."""
    if name in NODE_META:
        meta = NODE_META[name]
    elif name in TERMINAL_NODES:
        meta = {**TERMINAL_NODES[name], "desc": "", "sources": [], "produces": []}
    else:
        # 미등록(신규) 노드 폴백 — 트레이스가 깨지지 않도록 보장
        meta = {
            "label": name.replace("_", " ").title(),
            "icon": "🔹",
            "desc": "(메타데이터 미등록 노드 — trace_meta.NODE_META 에 추가하면 상세 표시)",
            "sources": [],
            "produces": [],
        }
    return {
        "label": meta.get("label", name),
        "icon": meta.get("icon", "🔹"),
        "desc": meta.get("desc", ""),
        "sources": meta.get("sources", []),
        "source_labels": [SOURCE_LABELS.get(s, s) for s in meta.get("sources", [])],
        "produces": meta.get("produces", []),
    }


def _shorten(value: Any) -> Any:
    if isinstance(value, str) and len(value) > _MAX_PREVIEW:
        return value[:_MAX_PREVIEW] + f"\n… (총 {len(value):,}자, 이하 생략)"
    return value


def redact_update(update: dict | None) -> dict:
    """State 델타를 JSON 직렬화 가능하고 화면 표시에 적합하게 정리한다."""
    if not update:
        return {}
    clean: dict[str, Any] = {}
    for key, value in update.items():
        if key in ("messages", "node_details"):
            # messages: 직렬화 불가 / node_details: detail 로 별도 표기하므로 제외
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            clean[key] = _shorten(value)
        else:
            clean[key] = _shorten(str(value))
    return clean


def extract_detail(update: dict | None) -> dict | None:
    """노드가 기록한 진단 레코드(node_details)의 마지막 항목을 꺼낸다."""
    if not update:
        return None
    records = update.get("node_details")
    if isinstance(records, list) and records:
        rec = records[-1]
        # value 들도 너무 길면 줄인다
        items = [
            {"label": it.get("label", ""), "value": _shorten(it.get("value", ""))}
            for it in rec.get("items", [])
        ]
        return {"node": rec.get("node"), "headline": rec.get("headline", ""), "items": items}
    return None


def summarize_update(node: str, update: dict | None) -> dict[str, Any]:
    """노드의 State 델타를 '무엇이 어떻게 정제되었는가' 사람이 읽는 요약으로 변환."""
    update = update or {}
    lines: list[str] = []

    # 의도 분석 결과
    extracted = {
        k: update.get(k)
        for k in ("country", "purpose", "duration", "profession")
        if update.get(k)
    }
    if extracted:
        parts = [f"{FIELD_KO.get(k, k)}={v}" for k, v in extracted.items()]
        lines.append("자연어 → 구조화 추출: " + ", ".join(parts))
    if update.get("is_exception"):
        lines.append(f"예외 상황 감지: {update.get('exception_type')}")

    # 검색 컨텍스트
    if "search_results" in update:
        sr = update.get("search_results")
        if sr:
            blocks = sr.count("[") if isinstance(sr, str) else 0
            lines.append(
                f"검색 컨텍스트 {len(sr):,}자 확보"
                + (f" (문서 블록 ≈ {blocks}개)" if blocks else "")
            )
        else:
            lines.append("검색 결과 없음 → 폴백 경로로 분기")

    # 최종 응답
    if update.get("final_response"):
        fr = update["final_response"]
        lines.append(f"LLM 종합 → 최종 답변 {len(fr):,}자 생성")

    if not lines:
        lines.append("상태 변화 없음")

    return {"lines": lines}
