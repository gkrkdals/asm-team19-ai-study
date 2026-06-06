"""
키워드 없는 상황 변경 시나리오 검증 — run_no_keyword_status
══════════════════════════════════════════════════════════════════════════
목적:
  status_change 탐지가 키워드/정규식 기반(하드코딩)이므로,
  '전환', '바꾸', '신분변경' 등 등록된 키워드 없이도
  문맥상 비자 상태 변경 상황인 5개 시나리오를 실행해
  시스템이 어떻게 처리하는지 투명하게 기록한다.

기대 결과:
  - exception_handler 로 가지 않음 (키워드 없으므로 예외 라우팅 미발동)
  - visa_rag_search / web_search_tool 로 라우팅되어 일반 비자 안내 제공
  - 이는 "버그"가 아니라 키워드 기반 탐지의 알려진 한계임

사용:
  cd asm-team19-ai-study
  python tests/run_no_keyword_status.py
══════════════════════════════════════════════════════════════════════════
"""
import httpx, json, time, sys

API = "http://localhost:8000"

# ── 5개 시나리오: 키워드 없이 문맥만으로 상태 변경을 암시 ──────────────────
SCENARIOS = [
    {
        "id": "NK-01",
        "label": "US: F-1 졸업 → H-1B 스폰서 (키워드: 없음)",
        "note": "implicit F-1→H-1B without '전환/변경' keywords",
        "message": (
            "미국에서 F-1 비자로 컴퓨터공학 석사를 마쳤어요. "
            "졸업 후 현지 IT 기업에서 고용 제안을 받았고 H-1B 피티션을 "
            "진행해 준다고 하는데, 졸업 후 어떤 절차가 필요한가요?"
        ),
    },
    {
        "id": "NK-02",
        "label": "AU: 학생 비자 졸업 → 취업 (키워드: 없음)",
        "note": "implicit student→work visa without '신분/전환' keywords",
        "message": (
            "호주에서 어학원을 3개월 다녔고 어학원 수료 후에도 "
            "멜버른 현지 카페에서 풀타임으로 일하고 싶은데 "
            "계속 머물 방법이 있을까요?"
        ),
    },
    {
        "id": "NK-03",
        "label": "DE: 구직 비자 체류 → 취업 확정 (키워드: 없음)",
        "note": "implicit job-seeker visa→work permit without '변경' keywords",
        "message": (
            "독일 구직 비자(Jobseekervisum)로 체류 중인데 "
            "베를린 스타트업에서 채용이 확정됐어요. "
            "지금부터 어떻게 해야 일을 시작할 수 있나요?"
        ),
    },
    {
        "id": "NK-04",
        "label": "JP: 워킹홀리데이 → 정직원 제안 (키워드: 없음)",
        "note": "implicit WH→employment permit without '전환' keywords",
        "message": (
            "일본 워킹홀리데이 비자로 도쿄 카페에서 아르바이트 중인데 "
            "사장님이 정직원으로 계속 일해달라고 제안을 하셨어요. "
            "장기적으로 일하려면 무엇이 필요한지 궁금해요."
        ),
    },
    {
        "id": "NK-05",
        "label": "CA: 학생 → PGWP → 영주권 경로 (키워드: 없음)",
        "note": "implicit multi-step status change path without change keywords",
        "message": (
            "캐나다 대학교를 졸업했고 PGWP(졸업 후 취업 허가)를 받아서 "
            "지금 소프트웨어 개발자로 일하고 있어요. "
            "영주권을 받으려면 앞으로 어떻게 준비해야 하나요?"
        ),
    },
]


def chat_once(message: str) -> dict:
    """단일 메시지를 스트리밍 API로 전송 후 결과 수집."""
    route, acc = [], ""
    is_followup, is_visa = None, None
    exception_type, country = None, None

    with httpx.stream(
        "POST", f"{API}/chat/stream",
        json={"message": message, "session_id": "nk_test"},
        timeout=90,
    ) as r:
        buf = ""
        for chunk in r.iter_text():
            buf += chunk
            while "\n\n" in buf:
                block, buf = buf.split("\n\n", 1)
                for line in block.split("\n"):
                    if not line.startswith("data:"):
                        continue
                    try:
                        ev = json.loads(line[5:].strip())
                        t = ev.get("type")
                        if t == "node":
                            route.append(ev["node"])
                        elif t == "token":
                            acc += ev.get("text", "")
                        elif t == "slots":
                            s = ev.get("slots") or {}
                            country = s.get("country")
                            exception_type = s.get("exception_type")
                        elif t == "meta":
                            if "is_followup" in ev:
                                is_followup = ev["is_followup"]
                            if "is_visa_related" in ev:
                                is_visa = ev["is_visa_related"]
                        elif t == "done":
                            acc = ev.get("final_response", acc)
                            if "is_followup" in ev:
                                is_followup = ev["is_followup"]
                            if "is_visa_related" in ev:
                                is_visa = ev["is_visa_related"]
                            s = ev.get("slots") or {}
                            if s.get("country"):
                                country = s["country"]
                            if s.get("exception_type"):
                                exception_type = s["exception_type"]
                    except Exception:
                        pass
    return {
        "route": route,
        "answer": acc,
        "is_followup": is_followup,
        "is_visa": is_visa,
        "country": country,
        "exception_type": exception_type,
    }


ROUTE_SHORT = {
    "intent_classifier": "intent",
    "visa_rag_search": "RAG",
    "web_search_tool": "WEB",
    "exception_handler": "EXC",
    "general_chat": "CHAT",
    "response_formatter": "RESP",
    "search_quality_gate": "GATE",
    "query_refiner": "REFINE",
    "knowledge_writer": "LEARN",
}


def short_route(route):
    return " → ".join(ROUTE_SHORT.get(n, n) for n in route)


def main():
    # 서버 확인
    try:
        httpx.get(f"{API}/health", timeout=5).raise_for_status()
    except Exception as e:
        print(f"❌ 백엔드 연결 실패: {e}")
        sys.exit(1)

    print()
    print("=" * 72)
    print("  키워드 없는 상황 변경 시나리오 — 탐지 한계 투명성 검증")
    print("=" * 72)
    print("  [목적] '전환/변경/신분변경' 키워드 없이 문맥상 비자 상태 변경인 경우")
    print("  → exception_handler 비활성, 일반 비자 안내 경로로 처리됨을 확인")
    print()

    results = []
    for sc in SCENARIOS:
        print(f"[{sc['id']}] {sc['label']}")
        print(f"         → {sc['note']}")

        res = chat_once(sc["message"])

        hit_exc = "exception_handler" in res["route"]
        route_str = short_route(res["route"])

        verdict = "⚠️  EXC 발동 (예상 밖)" if hit_exc else "✅ 일반 경로 (예상대로)"
        print(f"         route   : {route_str}")
        print(f"         country : {res['country']}  exception: {res['exception_type']}")
        print(f"         verdict : {verdict}")
        print(f"         답변 앞 80자 : {(res['answer'] or '')[:80].strip()}")
        print()

        results.append({
            "id": sc["id"],
            "label": sc["label"],
            "note": sc["note"],
            "route": res["route"],
            "route_short": route_str,
            "country": res["country"],
            "exception_type": res["exception_type"],
            "is_followup": res["is_followup"],
            "hit_exception_handler": hit_exc,
            "verdict": "unexpected_exc" if hit_exc else "normal_path",
            "answer_preview": (res["answer"] or "")[:300],
        })
        time.sleep(0.5)

    # ── 요약 ────────────────────────────────────────────────────────────────
    normal = sum(1 for r in results if not r["hit_exception_handler"])
    exc_hit = len(results) - normal

    print("=" * 72)
    print(f"  결과 요약: {normal}/{len(results)} 시나리오 → 일반 경로(예상대로)")
    if exc_hit:
        print(f"  ⚠️  {exc_hit}개 시나리오에서 exception_handler 발동 (키워드 오감지?)")
    print()
    print("  [해석]")
    print("  • EXC 미발동(✅) = 키워드 기반 탐지가 FP 없이 올바르게 동작함")
    print("  • 단, 문맥상 비자 변경 상황임에도 exception_handler 경로를 타지 않으므로")
    print("    키워드 없는 상태변경은 일반 비자 안내로 처리됨 — 알려진 한계")
    print("  • 비자 서비스 특성상 이런 표현에서 FP가 발생할 맥락이 적어 실용적으로 수용")
    print("=" * 72)

    # 결과 저장
    import os
    out_path = os.path.join(os.path.dirname(__file__), "results_no_keyword_status.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "summary": {
                    "total": len(results),
                    "normal_path": normal,
                    "exception_hit": exc_hit,
                    "note": "키워드 없는 상태변경 탐지 한계 투명성 검증",
                },
                "rows": results,
            },
            f, ensure_ascii=False, indent=2,
        )
    print(f"\n📊 결과 저장: {out_path}")

    # 세션 정리
    try:
        httpx.delete(f"{API}/sessions/nk_test", timeout=5)
    except Exception:
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
