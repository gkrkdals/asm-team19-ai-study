"""
멀티턴 심화 검증 실행기 — run_multiturn_v50.py
═══════════════════════════════════════════════════════════════════════
- 각 시나리오를 독립 세션으로 실행 (세션 격리 검증 포함)
- Group D: /chat/followups 결과에서 후속 질문을 자동 선택해 10+회 연속 대화
- 결과: tests/results_multiturn_v50.json + .log
═══════════════════════════════════════════════════════════════════════
"""
import sys, os, json, time, uuid, httpx, re
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "api"))

API  = "http://localhost:8000"
OUTJ = os.path.join(os.path.dirname(__file__), "results_multiturn_v50.json")
OUTL = os.path.join(os.path.dirname(__file__), "results_multiturn_v50.log")

TURN_TIMEOUT   = 120   # 초
BETWEEN_TURNS  = 1.2   # 초

log_lines = []

def log(msg):
    print(msg)
    log_lines.append(msg)

def api_call(method, path, body=None):
    url = f"{API}{path}"
    r = httpx.request(method, url, json=body, timeout=30)
    r.raise_for_status()
    return r.json()

def stream_chat(message, session_id, history):
    """SSE 스트리밍으로 노드 경로와 followups를 추출."""
    route, acc, followups = [], "", []
    with httpx.stream(
        "POST", f"{API}/chat/stream",
        json={"message": message, "session_id": session_id, "history": history},
        timeout=TURN_TIMEOUT,
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
                            elif t == "done":
                                acc = ev.get("final_response", acc)
                        except Exception:
                            pass
    # followups 별도 요청
    try:
        hist_slice = history[-6:] + [{"role": "user", "content": message},
                                     {"role": "assistant", "content": acc[:400]}]
        fdata = api_call("POST", "/chat/followups", {"history": hist_slice})
        followups = fdata.get("suggestions", [])
    except Exception:
        followups = []
    return route, acc, followups

def check_nodes(route, expected_nodes):
    """expected_nodes 중 하나라도 route에 포함되면 pass."""
    return any(n in route for n in expected_nodes)

def run_scenario(scenario_id, phase, turns, note):
    sid = f"mt_{scenario_id}_{uuid.uuid4().hex[:8]}"
    try:
        s = api_call("POST", "/sessions", {"title": scenario_id})
        sid = s.get("id", sid)
    except Exception:
        pass

    log(f"\n{'─'*80}")
    log(f"  [{phase}] {scenario_id}")
    log(f"  노트: {note}")
    log(f"  세션: {sid}")
    log(f"{'─'*80}")

    history = []
    turn_results = []
    last_followups = []
    all_pass = True

    for ti, (msg, expected_nodes, desc) in enumerate(turns):
        # __followup__ 처리: 이전 응답의 followup 칩 중 첫 번째 선택
        if msg == "__followup__":
            if not last_followups:
                log(f"  턴 {ti+1} [{desc}]: ⚠️ followup 없음 — 기본 질문으로 대체")
                msg = "더 자세히 알려주세요"
            else:
                msg = last_followups[0]
                log(f"  턴 {ti+1} [{desc}]: 🔗 followup 선택 → '{msg[:40]}'")
        else:
            log(f"  턴 {ti+1} [{desc}]: '{msg[:50]}'")

        try:
            route, response, followups = stream_chat(msg, sid, history)
            last_followups = followups
            passed = check_nodes(route, expected_nodes)
            status = "✅" if passed else "⚠️"
            all_pass = all_pass and passed
            route_str = " → ".join(n.replace("intent_classifier","intent")
                                    .replace("visa_rag_search","rag")
                                    .replace("web_search_tool","web")
                                    .replace("knowledge_writer","writer")
                                    .replace("response_formatter","resp")
                                    .replace("exception_handler","exc")
                                    .replace("general_chat","general")
                                   for n in route)
            log(f"       {status} route: {route_str}")
            log(f"          followups({len(followups)}): {followups[:2]}")
            turn_results.append({
                "turn": ti + 1, "desc": desc, "msg": msg,
                "route": route, "passed": passed,
                "followups": followups,
                "response_preview": response[:120],
            })
        except Exception as e:
            log(f"       ❌ 오류: {e}")
            turn_results.append({"turn": ti+1, "desc": desc, "msg": msg,
                                  "route": [], "passed": False, "error": str(e)})
            all_pass = False

        history.append({"role": "user", "content": msg})
        history.append({"role": "assistant", "content":
                         turn_results[-1].get("response_preview", "")})
        time.sleep(BETWEEN_TURNS)

    n_pass = sum(1 for t in turn_results if t.get("passed"))
    n_total = len(turn_results)
    pct = n_pass / n_total * 100 if n_total else 0
    log(f"  ▶ 결과: {n_pass}/{n_total} ({pct:.0f}%)"
        + (" ✅" if all_pass else " ⚠️"))
    return {
        "id": scenario_id, "phase": phase, "note": note, "sid": sid,
        "turns": turn_results,
        "pass": n_pass, "total": n_total, "pct": round(pct, 1),
        "all_pass": all_pass,
    }

def main():
    from scenarios_multiturn_v50 import ALL_SCENARIOS

    assert httpx.get(f"{API}/health", timeout=5).status_code == 200, "API 미응답"

    log("=" * 80)
    log("VisaGuide AI — 멀티턴 심화 검증 v50")
    log(f"총 시나리오: {len(ALL_SCENARIOS)}")
    log("=" * 80)

    records, start = [], time.time()

    for scenario_id, phase, turns, note in ALL_SCENARIOS:
        rec = run_scenario(scenario_id, phase, turns, note)
        records.append(rec)

    # ── 종합 통계 ────────────────────────────────────────────────────
    elapsed = round(time.time() - start)
    by_phase = {}
    for r in records:
        p = r["phase"]
        if p not in by_phase:
            by_phase[p] = {"pass": 0, "total": 0}
        by_phase[p]["pass"]  += r["pass"]
        by_phase[p]["total"] += r["total"]

    total_pass  = sum(r["pass"]  for r in records)
    total_total = sum(r["total"] for r in records)
    overall_pct = total_pass / total_total * 100 if total_total else 0

    log("\n" + "=" * 80)
    log("종합 결과")
    log("─" * 60)
    for phase, s in by_phase.items():
        pct = s["pass"] / s["total"] * 100 if s["total"] else 0
        log(f"  {phase:20s}: {s['pass']:3d}/{s['total']:3d} ({pct:.0f}%)")
    log(f"  {'전체':20s}: {total_pass:3d}/{total_total:3d} ({overall_pct:.0f}%)")
    log(f"  실행 시간: {elapsed}초")
    log("=" * 80)

    # ── 실패 케이스 요약 ─────────────────────────────────────────────
    log("\n실패한 턴 상세:")
    for r in records:
        failed = [t for t in r["turns"] if not t.get("passed")]
        if failed:
            log(f"  [{r['phase']}] {r['id']}")
            for t in failed:
                route = " → ".join(t.get("route", []))
                log(f"    턴{t['turn']} '{t['msg'][:35]}' → {route or '(없음)'}")

    result = {
        "summary": {
            "total_scenarios": len(records),
            "total_turns": total_total,
            "passed_turns": total_pass,
            "overall_pct": round(overall_pct, 1),
            "elapsed_sec": elapsed,
            "by_phase": by_phase,
        },
        "records": records,
    }
    with open(OUTJ, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    with open(OUTL, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))
    print(f"\n📊 결과 저장: {OUTJ}")
    print(f"📝 로그 저장: {OUTL}")

if __name__ == "__main__":
    main()
