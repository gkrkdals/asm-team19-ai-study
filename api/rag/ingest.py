import os
import json
import hashlib
import logging
from rag.vectorstore import get_collection, reset_collection

logger = logging.getLogger(__name__)

COUNTRIES = {
    "US": "미국",
    "JP": "일본",
    "GB": "영국",
    "CA": "캐나다",
    "AU": "호주",
    "DE": "독일",
}


def visa_to_text(visa: dict, country_code: str) -> str:
    """비자 dict를 검색 가능한 텍스트로 변환한다."""
    lines = [
        f"국가: {COUNTRIES.get(country_code, country_code)} ({country_code})",
    ]

    if visa.get("visa_type"):
        lines.append(f"비자 종류: {visa['visa_type']}")
    if visa.get("visa_code"):
        lines.append(f"비자 코드: {visa['visa_code']}")
    if visa.get("category"):
        lines.append(f"카테고리: {visa['category']}")
    if visa.get("subcategory"):
        lines.append(f"세부 분류: {visa['subcategory']}")

    max_dur = visa.get("max_duration_months")
    if max_dur:
        lines.append(f"최대 체류 기간: {max_dur}개월")

    if visa.get("is_renewable") is not None:
        lines.append(f"갱신 가능: {'예' if visa['is_renewable'] else '아니오'}")
    if visa.get("requires_sponsor") is not None:
        lines.append(f"스폰서 필요: {'예' if visa['requires_sponsor'] else '아니오'}")
    if visa.get("work_authorized") is not None:
        lines.append(f"취업 허용: {'예' if visa['work_authorized'] else '아니오'}")
    if visa.get("annual_quota"):
        lines.append(f"연간 쿼터: {visa['annual_quota']}")

    criteria = visa.get("eligibility_criteria")
    if criteria:
        if isinstance(criteria, list) and criteria:
            lines.append("자격 요건:\n" + "\n".join(f"  - {c}" for c in criteria))
        elif isinstance(criteria, str):
            lines.append(f"자격 요건: {criteria}")

    docs = visa.get("key_documents")
    if docs:
        if isinstance(docs, list) and docs:
            lines.append("필요 서류:\n" + "\n".join(f"  - {d}" for d in docs))
        elif isinstance(docs, str):
            lines.append(f"필요 서류: {docs}")

    if visa.get("processing_note"):
        lines.append(f"처리 참고사항: {visa['processing_note']}")
    if visa.get("source_url"):
        lines.append(f"공식 출처: {visa['source_url']}")

    return "\n".join(lines)


def _ingest_country(data_path: str, country_code: str, collection) -> int:
    all_visas_path = os.path.join(data_path, country_code, "_all_visas.json")
    if not os.path.exists(all_visas_path):
        logger.warning(f"No _all_visas.json for {country_code}, skipping.")
        return 0

    with open(all_visas_path, encoding="utf-8") as f:
        visas = json.load(f)

    documents, metadatas, ids = [], [], []
    for visa in visas:
        text = visa_to_text(visa, country_code)
        doc_id = hashlib.md5(
            f"{country_code}:{visa.get('visa_code', '')}".encode()
        ).hexdigest()
        documents.append(text)
        metadatas.append({
            "country_code": country_code,
            "country_name": COUNTRIES.get(country_code, country_code),
            "visa_code": visa.get("visa_code") or "",
            "visa_type": visa.get("visa_type") or "",
            "category": visa.get("category") or "",
            "source_url": visa.get("source_url") or "",
        })
        ids.append(doc_id)

    if documents:
        collection.upsert(documents=documents, metadatas=metadatas, ids=ids)
        logger.info(f"[{country_code}] Ingested {len(documents)} visa records.")

    return len(documents)


def ingest_all(force: bool = False) -> int:
    data_path = os.getenv("DATA_PATH", os.path.join(os.path.dirname(__file__), "../../data/visas"))
    data_path = os.path.abspath(data_path)

    if force:
        reset_collection()
        logger.info("Collection reset.")

    collection = get_collection()

    if not force and collection.count() > 0:
        logger.info(f"Collection already has {collection.count()} docs, skipping ingestion. Use force=True to re-ingest.")
        return collection.count()

    total = 0
    for country_code in COUNTRIES:
        try:
            total += _ingest_country(data_path, country_code, collection)
        except Exception as e:
            logger.error(f"Ingestion error for {country_code}: {e}")

    logger.info(f"Ingestion complete: {total} total documents.")
    return total
