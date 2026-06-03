import os
import time
import hashlib
import logging
from typing import List, Optional
import chromadb

logger = logging.getLogger(__name__)

COLLECTION_NAME = "visa_information"

_client = None
_collection = None


def get_client():
    global _client
    if _client is None:
        host = os.getenv("CHROMA_HOST", "")
        if not host or host in ("local", "localhost") and os.getenv("CHROMA_PORT", "") in ("", "local"):
            # 로컬 영속 클라이언트 (Docker 없이 실행 시)
            data_dir = os.path.join(os.path.dirname(__file__), "../../chroma_data")
            os.makedirs(data_dir, exist_ok=True)
            _client = chromadb.PersistentClient(path=data_dir)
            logger.info("Using local PersistentClient for ChromaDB")
        else:
            port = int(os.getenv("CHROMA_PORT", "8000"))
            _client = chromadb.HttpClient(host=host, port=port)
            logger.info(f"Using ChromaDB HTTP client at {host}:{port}")
    return _client


def get_collection():
    global _collection
    if _collection is None:
        client = get_client()
        _collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def _query(where: Optional[dict], query: str, n_results: int) -> List[dict]:
    collection = get_collection()
    results = collection.query(query_texts=[query], n_results=n_results, where=where)
    if not results["documents"] or not results["documents"][0]:
        return []
    return [
        {"document": doc, "metadata": meta, "distance": dist}
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        )
    ]


def search_visas(
    query: str,
    country_code: Optional[str] = None,
    n_results: int = 5,
) -> List[dict]:
    """비자 문서(doc_type=visa)만 검색한다. 예외 규칙은 제외."""
    try:
        if country_code:
            where = {"$and": [
                {"country_code": {"$eq": country_code}},
                {"doc_type": {"$eq": "visa"}},
            ]}
        else:
            where = {"doc_type": {"$eq": "visa"}}
        return _query(where, query, n_results)
    except Exception as e:
        logger.error(f"Vector search error: {e}")
        return []


def search_exceptions(query: str, n_results: int = 3) -> List[dict]:
    """교차 예외 규칙(doc_type=exception_rule)을 국가 필터 없이 의미검색한다.

    쉥겐·환승·ETA·비자런·유효기간≠체류 등 비자 레코드만으로 답할 수 없는
    교차 규칙을 LLM 컨텍스트로 주입하기 위해 사용한다.
    """
    try:
        return _query({"doc_type": {"$eq": "exception_rule"}}, query, n_results)
    except Exception as e:
        logger.error(f"Exception rule search error: {e}")
        return []


def count_learned() -> int:
    """웹 검색으로 학습 저장된 문서 수(origin=web_search)."""
    try:
        collection = get_collection()
        res = collection.get(where={"origin": {"$eq": "web_search"}})
        return len(res.get("ids", []) or [])
    except Exception as e:
        logger.error(f"count_learned error: {e}")
        return 0


def add_learned_visa(
    country_code: str,
    content: str,
    *,
    purpose: str = "",
    query: str = "",
    source_urls: Optional[List[str]] = None,
) -> dict:
    """신뢰도 높은 웹 검색 결과를 비자 컬렉션에 '학습 문서'로 upsert 한다.

    doc_type='visa' 로 저장하므로 다음 동일 국가 질의 시 RAG 검색에 포함되어
    웹 검색을 건너뛰고 즉시 응답할 수 있다(점진적 지식 축적). origin='web_search'
    로 표시해 사전 적재된 공식 문서와 구분한다.

    Returns
    -------
    {"id", "chars", "sources", "is_new"}
    """
    collection = get_collection()
    cc = (country_code or "XX").upper()
    src = ", ".join([u for u in (source_urls or []) if u])
    doc_id = "web:" + hashlib.md5(f"{cc}:{purpose}:{query}".encode()).hexdigest()[:16]

    try:
        existed = collection.get(ids=[doc_id])
        is_new = not (existed and existed.get("ids"))
    except Exception:
        is_new = True

    text = (
        f"국가: {cc}\n"
        f"(웹 검색으로 학습된 비자 정보 · 목적: {purpose or '일반'})\n"
        f"검색어: {query}\n"
        f"출처: {src or '미상'}\n\n"
        f"{content}"
    )
    collection.upsert(
        documents=[text],
        metadatas=[{
            "doc_type": "visa",                       # 다음 RAG 검색에 포함
            "country_code": cc,
            "country_name": cc,
            "visa_code": "",
            "visa_type": f"웹 학습 정보({purpose or '일반'})",
            "category": "web_learned",
            "origin": "web_search",                   # 사전 적재 공식문서와 구분
            "source_url": src,
            "learned_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }],
        ids=[doc_id],
    )
    return {"id": doc_id, "chars": len(content or ""), "sources": source_urls or [], "is_new": is_new}


def reset_collection():
    global _collection
    client = get_client()
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    _collection = None
    get_collection()
