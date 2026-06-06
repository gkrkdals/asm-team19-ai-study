"""
저신뢰 영역 검증 실행기 — run_low_confidence
══════════════════════════════════════════════════════════════════════════
scenarios_low_confidence.py 의 45개 시나리오를 순서대로 실행하고
예상 결과와 실측 결과를 대조합니다.

사용:
    python tests/run_low_confidence.py           # 전체 실행
    python tests/run_low_confidence.py G1        # Group 1 만
    python tests/run_low_confidence.py G1 G2     # 복수 그룹

출력:
    - 콘솔: 시나리오별 ✅/❌ + 실패 원인
    - tests/results_low_confidence.json
══════════════════════════════════════════════════════════════════════════
"""
import httpx, json, sys, time, os
from scenarios_low_confidence import ALL_SCENARIOS, TOTAL

API = "http://localhost:8000"
REF_PHRASES = ["앞서", "앞선", "이전", "위에서", "말씀드린", "안내드린", "안내해 드린", "안내한"]


def chat(messages):
    """messages 목록을 주면 마지막 user 메시지를 현재 질문으로, 나머지를 history로 전송."""
    history = messages[:-1]
    last_msg = messages[-1]["content"]
    route, acc = [], ""
    is_followup, is_visa = None, None
    exception_type, country = None, None

    with httpx.stream(
        "POST", f"{API}/chat/stream",
        json={"message": last_msg, "session_id": "lc_verify", "history": history},
        timeout=120,
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


def judge(sc, res):
    failures = []
    route = res["route"]

    # 1) 필수 경로 포함 여부
    for node in sc.get("expected_route", []):
        if node not in route:
            failures.append(f"경로에 '{node}' 없음 (실측: {route})")

    # 2) 금지 경로 포함 여부
    for node in sc.get("forbidden_route", []):
        if node in route:
            failures.append(f"금지 노드 '{node}' 발견 (실측: {route})")

    # 3) is_followup 일치
    if sc["check_followup"] is not None:
        got = bool(res["is_followup"])
        exp = bool(sc["check_followup"])
        if got != exp:
            failures.append(f"is_followup 불일치: 기대={exp}, 실측={got}")

    # 4) exception_type 일치
    if sc["check_exception"] is not None:
        got = res["exception_type"]
        exp = sc["check_exception"]
        if (got or "").lower() != exp.lower():
            failures.append(f"exception_type 불일치: 기대={exp}, 실측={got}")
    elif sc["check_exception"] is None and sc.get("id", "").startswith(("G1", "G2")):
        # FP 방지 케이스: check_exception=None 이면 exception_type이 없어야 정상
        pass  # runner에서 FP 체크는 별도 로직 필요 시 추가

    # 5) country 일치
    if sc["check_country"] is not None:
        got = (res["country"] or "").upper()
        exp = sc["check_country"].upper()
        if got != exp:
            failures.append(f"country 불일치: 기대={exp}, 실측={got}")

    # 6) _extra_check: 응답에 참조 표현 포함 여부
    extra = sc.get("_extra_check")
    if extra == "response_has_ref":
        has_ref = any(p in (res["answer"] or "") for p in REF_PHRASES)
        if not has_ref:
            failures.append("응답에 상위 참조 표현 없음")

    return failures


def run_group(group_name, scenarios):
    total = len(scenarios)
    passed = 0
    rows = []

    print(f"\n{'=' * 70}")
    print(f"  {group_name}  ({total}개)")
    print("=" * 70)

    for sc in scenarios:
        result = chat(sc["messages"])
        failures = judge(sc, result)
        ok = len(failures) == 0
        if ok:
            passed += 1

        mark = "✅" if ok else "❌"
        route_str = " → ".join(
            n.replace("intent_classifier", "intent")
             .replace("visa_rag_search", "rag")
             .replace("web_search_tool", "web")
             .replace("response_formatter", "resp")
             .replace("exception_handler", "exc")
             .replace("general_chat", "chat")
            for n in result["route"]
        )
        print(f"\n[{sc['id']}] {mark}  {sc['description']}")
        print(f"         route: {route_str}")
        print(f"         country={result['country']}  exception={result['exception_type']}"
              f"  followup={result['is_followup']}")
        if failures:
            for f in failures:
                print(f"         ✗ {f}")

        rows.append({
            "group": group_name,
            "id": sc["id"],
            "description": sc["description"],
            "passed": ok,
            "failures": failures,
            "route": result["route"],
            "country": result["country"],
            "exception_type": result["exception_type"],
            "is_followup": result["is_followup"],
            "answer_preview": (result["answer"] or "")[:200],
        })
        time.sleep(0.5)

    print(f"\n  ▶ {group_name}: {passed}/{total} 통과")
    return rows, passed, total


def main():
    # 서버 확인
    try:
        httpx.get(f"{API}/health", timeout=5).raise_for_status()
    except Exception as e:
        print(f"❌ 백엔드 연결 실패: {e}")
        sys.exit(1)

    # 그룹 필터 (인자 없으면 전체)
    group_filter = set(arg.upper() for arg in sys.argv[1:]) if len(sys.argv) > 1 else set()

    all_rows, all_passed, all_total = [], 0, 0
    for group_name, scenarios in ALL_SCENARIOS.items():
        key = group_name.split("_")[0]  # "G1", "G2", ...
        if group_filter and key not in group_filter:
            continue
        rows, passed, total = run_group(group_name, scenarios)
        all_rows += rows
        all_passed += passed
        all_total += total

    print(f"\n{'=' * 70}")
    print(f"종합: {all_passed}/{all_total} 통과  ({all_passed/all_total*100:.1f}%)" if all_total else "실행된 시나리오 없음")
    print("=" * 70)

    # 그룹별 요약
    group_stats = {}
    for row in all_rows:
        g = row["group"]
        group_stats.setdefault(g, {"passed": 0, "total": 0})
        group_stats[g]["total"] += 1
        if row["passed"]:
            group_stats[g]["passed"] += 1
    for g, s in group_stats.items():
        bar = "█" * s["passed"] + "░" * (s["total"] - s["passed"])
        print(f"  {g}: {s['passed']}/{s['total']} [{bar}]")

    # 결과 저장
    out = {
        "summary": {
            "total": all_total,
            "passed": all_passed,
            "pass_rate": round(all_passed / all_total * 100, 1) if all_total else 0,
            "group_stats": {g: {**s, "rate": round(s["passed"]/s["total"]*100, 1)}
                            for g, s in group_stats.items()},
        },
        "rows": all_rows,
    }
    p = os.path.join(os.path.dirname(__file__), "results_low_confidence.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n📊 결과 저장: {p}")

    # 검증 세션 정리
    try:
        httpx.delete(f"{API}/sessions/lc_verify", timeout=5)
    except Exception:
        pass

    sys.exit(0 if all_passed == all_total else 1)


if __name__ == "__main__":
    main()
