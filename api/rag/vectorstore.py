import os
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


def search_visas(
    query: str,
    country_code: Optional[str] = None,
    n_results: int = 5,
) -> List[dict]:
    try:
        collection = get_collection()

        where = {"country_code": {"$eq": country_code}} if country_code else None

        results = collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where,
        )

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
    except Exception as e:
        logger.error(f"Vector search error: {e}")
        return []


def reset_collection():
    global _collection
    client = get_client()
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    _collection = None
    get_collection()
