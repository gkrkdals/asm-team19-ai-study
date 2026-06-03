"""
지식 학습 저장 노드(knowledge_writer).

신뢰도 게이트(search_quality_gate)가 'good'으로 판정한 웹 검색 결과를
ChromaDB 비자 컬렉션에 학습 문서로 upsert 한다. 다음에 같은 국가를 물으면
RAG 검색에 포함되어 웹 검색을 건너뛰고 즉시 응답할 수 있다(점진적 지식 축적).

리뷰 요청("비자 정보를 검색해 신뢰도가 높으면 ChromaDB에 데이터가 추가되도록
구성하고, 그 동작을 실시간 트레이스에서 보이도록 하라") 반영. 이 노드는
graph 에 포함되므로 토폴로지·타임라인에 자동으로 나타난다.
"""
import re
import logging
from agent.state import AgentState

logger = logging.getLogger(__name__)

_MIN_LEARN_LEN = 400


async def knowledge_writer(state: AgentState) -> dict:
    """고신뢰 웹 검색 컨텍스트를 ChromaDB 비자 컬렉션에 학습 저장(upsert)한다."""
    country = state.get("country") or ""
    purpose = state.get("purpose") or ""
    content = state.get("search_results") or ""
    quality = state.get("search_quality")
    query = state.get("web_query") or ""

    # 컨텍스트에서 출처 URL 추출(web_search_tool 이 "출처: <url>" 형태로 기록)
    urls = re.findall(r"출처:\s*(\S+)", content)

    should_store = bool(quality == "good" and country and len(content) >= _MIN_LEARN_LEN)
    stored = None
    if should_store:
        try:
            from rag.vectorstore import add_learned_visa
            stored = add_learned_visa(
                country, content, purpose=purpose, query=query, source_urls=urls
            )
        except Exception as e:  # noqa: BLE001
            logger.error("knowledge_writer upsert error: %s", e)

    if stored:
        status = (
            f"신규 학습 저장(국가={country})" if stored.get("is_new")
            else f"기존 학습 문서 갱신(국가={country})"
        )
        items = [
            {"label": "① 저장 판정", "value": "신뢰도 good → ChromaDB 비자 컬렉션에 upsert"},
            {"label": "② 문서 ID", "value": stored["id"]},
            {"label": "③ 국가/목적", "value": f"{country} / {purpose or '일반'}"},
            {"label": "④ 저장 분량", "value": f"{stored['chars']:,}자"},
            {"label": "⑤ 출처 URL", "value": "\n".join(urls) if urls else "미상"},
            {"label": "⑥ 결과", "value": status + " · 다음 동일국가 질의 시 RAG 즉시 활용"},
        ]
    else:
        reason = ("신뢰도 미달(good 아님)" if quality != "good"
                  else "국가 미상" if not country
                  else f"내용 부족({len(content)}자 < {_MIN_LEARN_LEN})")
        items = [
            {"label": "① 저장 판정", "value": f"저장 안 함 — {reason}"},
            {"label": "② 비고", "value": "낮은 신뢰도 정보는 학습하지 않아 DB 오염을 방지"},
        ]

    detail = {
        "node": "knowledge_writer",
        "headline": "고신뢰 웹검색 결과 → ChromaDB 학습 저장",
        "items": items,
    }
    return {"kb_written": (stored["id"] if stored else None), "node_details": [detail]}
