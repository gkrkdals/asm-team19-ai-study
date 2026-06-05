"""
신뢰도 종합 검증 실행기 — run_reliability_v70.py
═══════════════════════════════════════════════════════════════════════════
방법론(예상-실측 대조):
  1) 시나리오마다 코드에 "예상 분기(expected)"가 사전 기록돼 있다.
  2) 각 턴을 실제 실행해 라우팅(actual route)을 수집한다.
  3) actual 의 '핵심 분기 노드'를 추출해 expected 와 일치(match) 여부를 판정한다.
  4) 그룹별/전체 일치율을 집계하고, 불일치 건은 분석용으로 상세 기록한다.

결과: tests/results_reliability_v70.json + .log
═══════════════════════════════════════════════════════════════════════════
"""
import sys, os, json, time, uuid, httpx
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "api"))

API  = "http://localhost:8000"
OUTJ = os.path.join(os.path.dirname(__file__), "results_reliability_v70.json")
OUTL = os.path.join(os.path.dirname(__file__), "results_reliability_v70.log")

TURN_TIMEOUT  = 120
BETWEEN_TURNS = 0.8

# 핵심 분기 노드 우선순위(라우팅 결과에서 '대표 분기' 1개를 뽑는 규칙)
NODE_ABBR = {
    "visa_rag_search": "RAG", "web_search_tool": "WEB",
    "exception_handler": "EXC", "general_chat": "GEN",
    "response_formatter": "RESP",
}

log_lines = []
def log(m):
    print(m); log_lines.append(m)

def primary_branch(route):
    """라우팅 경로에서 대표 분기 노드를 추출."""
    s = set(route)
    if "exception_handler" in s: return "EXC"
    if "general_chat" in s:      return "GEN"
    if "visa_rag_search" in s:   return "RAG"
    if "web_search_tool" in s:   return "WEB"
    return "RESP"

def stream_chat(message, session_id, history):
    route, acc = [], ""
    with httpx.stream("POST", f"{API}/chat/stream",
                      json={"message": message, "session_id": session_id, "history": history},
                      timeout=TURN_TIMEOUT) as r:
        buf = ""
        for chunk in r.iter_text():
            buf += chunk
            while "\n\n" in buf:
                block, buf = buf.split("\n\n", 1)
                for line in block.split("\n"):
                    if line.startswith("data:"):
                        try:
                            ev = json.loads(line[5:].strip())
                            if ev.get("type") == "node": route.append(ev["node"])
                            elif ev.get("type") == "token": acc += ev.get("text", "")
                            elif ev.get("type") == "done": acc = ev.get("final_response", acc)
                        except Exception:
                            pass
    followups = []
    try:
        hist = history[-6:] + [{"role": "user", "content": message},
                               {"role": "assistant", "content": acc[:400]}]
        followups = httpx.post(f"{API}/chat/followups", json={"history": hist},
                               timeout=30).json().get("suggestions", [])
    except Exception:
        pass
    return route, acc, followups

def run_scenario(sid_name, group, turns, note):
    try:
        s = httpx.post(f"{API}/sessions", json={"title": sid_name}, timeout=15).json()
        sid = s.get("id", "s_" + uuid.uuid4().hex[:8])
    except Exception:
        sid = "s_" + uuid.uuid4().hex[:8]

    log(f"\n{'─'*78}\n  [{group}] {sid_name} — {note}")
    history, results, last_fu = [], [], []
    for ti, (msg, exp_node, exp_reason) in enumerate(turns):
        is_fu = (msg == "__followup__")
        if is_fu:
            msg = last_fu[0] if last_fu else "더 자세히 알려주세요"
        exp_abbr = NODE_ABBR.get(exp_node, exp_node)
        try:
            route, resp, fus = stream_chat(msg, sid, history)
            last_fu = fus
            act_abbr = primary_branch(route)
            match = (act_abbr == exp_abbr)
            mark = "✅" if match else "❌"
            log(f"   {mark} T{ti+1} exp={exp_abbr:4s} act={act_abbr:4s} | {msg[:42]}")
            results.append({
                "turn": ti+1, "is_followup": is_fu, "msg": msg,
                "expected": exp_abbr, "expected_reason": exp_reason,
                "actual": act_abbr, "actual_route": route, "match": match,
                "resp_preview": resp[:100],
            })
        except Exception as e:
            log(f"   ⚠️ T{ti+1} 오류: {e}")
            results.append({"turn": ti+1, "msg": msg, "expected": exp_abbr,
                            "actual": "ERR", "match": False, "error": str(e)})
        history.append({"role": "user", "content": msg})
        history.append({"role": "assistant", "content": results[-1].get("resp_preview", "")})
        time.sleep(BETWEEN_TURNS)

    n_match = sum(1 for r in results if r.get("match"))
    log(f"   → {n_match}/{len(results)} 일치")
    return {"id": sid_name, "group": group, "note": note, "sid": sid,
            "turns": results, "match": n_match, "total": len(results)}

def main():
    from scenarios_reliability_v70 import ALL
    assert httpx.get(f"{API}/health", timeout=5).status_code == 200

    log("=" * 78)
    log(f"신뢰도 종합 검증 v70 — {len(ALL)} 시나리오")
    log("=" * 78)

    records, start = [], time.time()
    for sid_name, group, turns, note in ALL:
        records.append(run_scenario(sid_name, group, turns, note))

    # 집계
    by_group = {}
    for r in records:
        g = r["group"]
        by_group.setdefault(g, {"match": 0, "total": 0, "scenarios": 0})
        by_group[g]["match"] += r["match"]
        by_group[g]["total"] += r["total"]
        by_group[g]["scenarios"] += 1
    tot_m = sum(r["match"] for r in records)
    tot_t = sum(r["total"] for r in records)
    overall = round(tot_m / tot_t * 100, 1) if tot_t else 0

    log("\n" + "=" * 78 + "\n종합 결과 (예상 vs 실측 일치율)\n" + "─" * 50)
    for g, v in by_group.items():
        pct = v["match"] / v["total"] * 100 if v["total"] else 0
        log(f"  {g:14s} {v['match']:3d}/{v['total']:3d} ({pct:5.1f}%)  [{v['scenarios']}개 시나리오]")
    log(f"  {'전체':14s} {tot_m:3d}/{tot_t:3d} ({overall:5.1f}%)")
    log(f"  소요: {round(time.time()-start)}초")

    # 불일치 상세
    log("\n불일치(예상≠실측) 상세:")
    mism = 0
    for r in records:
        bad = [t for t in r["turns"] if not t.get("match")]
        if bad:
            for t in bad:
                log(f"  [{r['group']}] {r['id']} T{t['turn']}: exp={t['expected']} act={t.get('actual')} | {t.get('msg','')[:36]}")
                mism += 1
    if not mism:
        log("  (없음 — 모든 턴이 예상과 일치)")

    out = {
        "summary": {
            "round": "v70 (Round 11)",
            "total_scenarios": len(records), "total_turns": tot_t,
            "matched_turns": tot_m, "overall_pct": overall,
            "elapsed_sec": round(time.time()-start),
            "by_group": by_group, "mismatches": mism,
        },
        "records": records,
    }
    json.dump(out, open(OUTJ, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    open(OUTL, "w", encoding="utf-8").write("\n".join(log_lines))
    print(f"\n📊 저장: {OUTJ}")

if __name__ == "__main__":
    main()
