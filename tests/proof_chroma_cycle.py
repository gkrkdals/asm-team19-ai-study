"""
ChromaDB 자가학습 사이클 라이브 증명 — proof_chroma_cycle
═══════════════════════════════════════════════════════════════════════════
목적: "신규 국가 첫 요청 → 웹검색 → ChromaDB 저장 → 재요청 시 DB에서 추출"
      전체 사이클을 DB 0건 상태의 진짜 신규 국가로 깨끗하게 증명한다.

검증 절차 (국가별):
  [0] BEFORE: ChromaDB 해당 국가 문서 수 == 0 확인
  [1] 1차 요청: 라우팅에 web_search_tool(+knowledge_writer) 등장 기대
  [2] AFTER : ChromaDB 해당 국가 문서 수 >= 1 증가 확인 (학습 저장 증명)
  [3] 2차 요청(재요청): visa_rag_search 등장 + web_search_tool 미등장 기대
                       (= DB에서 직접 추출, 웹검색 불필요 증명)

대상: DB에 0건인 신규 국가 4개 (아이슬란드/룩셈부르크/에스토니아/우루과이)
═══════════════════════════════════════════════════════════════════════════
"""
import sys, os, json, time, httpx

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "api"))

API      = "http://localhost:8000"
LOG_JSON = os.path.join(os.path.dirname(__file__), "results_chroma_cycle.json")

# (국가코드, 한글, 첫요청, 재요청)
CASES = [
    ("IS", "아이슬란드", "아이슬란드에서 취업비자를 받으려면 어떤 조건이 필요한가요?",
                         "아이슬란드 취업비자 자격 요건 다시 정리해줘"),
    ("LU", "룩셈부르크", "룩셈부르크 취업비자 신청 절차가 어떻게 되나요?",
                         "룩셈부르크 취업비자 신청 방법 다시 알려줘"),
    ("EE", "에스토니아", "에스토니아 디지털 노마드 비자 조건은 무엇인가요?",
                         "에스토니아 디지털 노마드 비자 요건 한번 더 정리해줘"),
    ("UY", "우루과이",   "우루과이에서 장기 거주하려면 어떤 비자가 필요한가요?",
                         "우루과이 장기 거주 비자 조건 다시 설명해줘"),
]

WAIT_AFTER_FIRST = 4   # 학습 저장 반영 대기(초)


def count_docs(cc: str) -> int:
    """ChromaDB에서 해당 국가 코드 문서 수."""
    from rag.vectorstore import get_collection
    col = get_collection()
    data = col.get(include=["metadatas"])
    return sum(
        1 for m in data["metadatas"]
        if (m.get("country_code") or m.get("country") or "").upper() == cc
    )


def route_of(msg: str, sid: str, timeout: int = 150) -> list[str]:
    """단일 요청의 노드 경로."""
    route = []
    with httpx.stream(
        "POST", f"{API}/chat/stream",
        json={"message": msg, "session_id": sid, "history": []},
        timeout=timeout,
    ) as r:
        buf = ""
        for chunk in r.iter_text():
            buf += chunk
            while "\n\n" in buf:
                block, buf = buf.split("\n\n", 1)
                for line in block.split("\n"):
                    if line.startswith("data:"):
                        try:
                            ev = json.loads(line[5:].strip())
                            if ev.get("type") == "node":
                                route.append(ev["node"])
                        except Exception:
                            pass
    return route


def fmt(route: list[str]) -> str:
    return " → ".join(
        n.replace("_classifier","").replace("_search","")
         .replace("_handler","").replace("_formatter","")
         .replace("_tool","").replace("_gate","≥").replace("_writer","✍")
        for n in route
    )


def main():
    # 헬스 체크
    assert httpx.get(f"{API}/health", timeout=5).status_code == 200

    print("="*100)
    print("ChromaDB 자가학습 사이클 라이브 증명 — DB 0건 신규 국가 4개")
    print("="*100)

    records = []
    for cc, ko, q1, q2 in CASES:
        print(f"\n{'─'*100}\n  [{cc}] {ko}\n{'─'*100}")

        before = count_docs(cc)
        print(f"  [0] BEFORE  DB 문서 수: {before}건  {'✅ 신규(0건)' if before==0 else '⚠️ 이미 보유'}")

        r1 = route_of(q1, f"cycle_{cc}_1")
        has_web = "web_search_tool"  in r1
        has_kw  = "knowledge_writer" in r1
        print(f"  [1] 1차 요청 경로: {fmt(r1)}")
        print(f"      └ web_search_tool={has_web}  knowledge_writer={has_kw}")

        print(f"  ... 학습 반영 대기 {WAIT_AFTER_FIRST}초 ...")
        time.sleep(WAIT_AFTER_FIRST)

        after = count_docs(cc)
        grew  = after > before
        print(f"  [2] AFTER   DB 문서 수: {after}건  {'✅ 증가(+%d) → 학습 저장됨' % (after-before) if grew else '❌ 변화 없음'}")

        r2 = route_of(q2, f"cycle_{cc}_2")
        rag_hit = "visa_rag_search" in r2
        no_web  = "web_search_tool" not in r2
        print(f"  [3] 재요청 경로:   {fmt(r2)}")
        print(f"      └ visa_rag_search={rag_hit}  웹검색없음={no_web}  "
              f"{'✅ DB에서 직접 추출' if (rag_hit and no_web) else '⚠️ 부분 충족'}")

        # 사이클 성공 판정
        cycle_ok = (before == 0) and grew and rag_hit and no_web
        print(f"  ▶ 사이클 판정: {'✅ 완전 증명' if cycle_ok else '⚠️ 부분'}")

        records.append({
            "cc": cc, "ko": ko,
            "before": before, "after": after, "grew": grew,
            "first_route": r1, "first_web": has_web, "first_kw": has_kw,
            "recall_route": r2, "recall_rag": rag_hit, "recall_no_web": no_web,
            "cycle_proven": cycle_ok,
        })

    # 종합
    proven = sum(1 for r in records if r["cycle_proven"])
    stored = sum(1 for r in records if r["grew"])
    recall = sum(1 for r in records if r["recall_rag"] and r["recall_no_web"])
    print(f"\n{'='*100}")
    print("종합")
    print(f"{'─'*60}")
    print(f"  완전 사이클 증명:        {proven}/{len(records)}")
    print(f"  학습 저장(DB 증가):      {stored}/{len(records)}")
    print(f"  재요청 DB추출(웹검색없음): {recall}/{len(records)}")
    print(f"{'='*100}")

    with open(LOG_JSON, "w", encoding="utf-8") as f:
        json.dump({
            "summary": {"total": len(records), "cycle_proven": proven,
                        "stored": stored, "recall_only": recall},
            "records": records,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n📊 JSON 저장: {LOG_JSON}")


if __name__ == "__main__":
    main()
