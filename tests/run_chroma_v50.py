"""
ChromaDB 재검색 증명 + 개선 영역 검증 실행기 — v50
───────────────────────────────────────────────────
실행: python3 tests/run_chroma_v50.py
결과: tests/results_chroma_v50.log  +  tests/results_chroma_v50.json

핵심 검증 포인트 (Phase B)
  B1 요청 후 B2 요청을 실행했을 때, 같은 국가에 대한
  visa_rag_search 경로 비율이 높아야 한다 = ChromaDB 학습이 실제 동작함.
  B1 에서 knowledge_writer 가 실행되고,
  B2 에서 web_search_tool 없이 visa_rag_search → response 이면 완벽.
"""
import json, httpx, time, sys, os
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from tests.scenarios_chroma_v50 import (
    ALL_50, PHASE_META, PHASE_B1, PHASE_B2,
    PH_A1, PH_A2, PH_A3, PH_B1, PH_B2,
)

API      = "http://localhost:8000"
LOG_FILE = os.path.join(os.path.dirname(__file__), "results_chroma_v50.log")
JSON_FILE = os.path.join(os.path.dirname(__file__), "results_chroma_v50.json")

# B1 실행 후 ChromaDB 인덱스가 반영되기까지 짧은 대기
B1_B2_WAIT_SEC = 3


def query_route(msg: str, sid: str, history=None, timeout: int = 120) -> list[str]:
    route = []
    try:
        with httpx.stream(
            "POST", f"{API}/chat/stream",
            json={"message": msg, "session_id": sid, "history": history or []},
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
    except Exception as e:
        route.append(f"ERROR:{e!s:.60}")
    return route


def run_phase(cases, phase_name: str, output_log, idx_offset: int = 0) -> list[dict]:
    records = []
    print(f"\n{'─'*100}")
    print(f"  {phase_name} ({len(cases)}개)")
    print(f"{'─'*100}")
    output_log.write(f"\n{'─'*100}\n  {phase_name} ({len(cases)}개)\n{'─'*100}\n")

    for i, (msg, ph, expects, history, note) in enumerate(cases, 1):
        t0      = time.time()
        route   = query_route(msg, f"chroma_{ph}_{i:03d}", history)
        elapsed = time.time() - t0
        passed  = any(n in route for n in expects)

        path = " → ".join(
            n.replace("_classifier","").replace("_search","")
             .replace("_handler","").replace("_formatter","")
             .replace("_tool","").replace("_gate","≥")
             .replace("_writer","✍")
            for n in route[:5]
        )
        status = "✅" if passed else "❌"
        line = f"{idx_offset+i:3d}  {status}  {ph:22s}  {msg[:45]:45s}  {path}"
        print(line)
        output_log.write(line + "\n")

        records.append({
            "no": idx_offset + i, "msg": msg, "phase": ph,
            "expects": expects, "route": route,
            "passed": passed, "elapsed_s": round(elapsed, 1), "note": note,
        })
    return records


def summarize(records: list[dict], output_log) -> dict:
    by_phase = defaultdict(list)
    for r in records:
        by_phase[r["phase"]].append(r["passed"])

    # B2 ChromaDB 재활용 분석
    b1_records = [r for r in records if r["phase"] == PH_B1]
    b2_records = [r for r in records if r["phase"] == PH_B2]

    b1_kw_runs  = sum(1 for r in b1_records if "knowledge_writer" in r["route"])
    b1_web_runs = sum(1 for r in b1_records if "web_search_tool"  in r["route"])
    b2_rag_only = sum(
        1 for r in b2_records
        if "visa_rag_search" in r["route"] and "web_search_tool" not in r["route"]
    )
    b2_rag_hit  = sum(1 for r in b2_records if "visa_rag_search" in r["route"])

    total  = len(records)
    n_pass = sum(r["passed"] for r in records)
    overall = 100 * n_pass / total

    sep = "\n" + "=" * 100 + "\n"
    print(sep)
    output_log.write(sep)

    lines = [
        "Phase별 신뢰도",
        "-" * 80,
    ]
    for ph, results in sorted(by_phase.items()):
        n_t = len(results); n_p = sum(results)
        pct = 100 * n_p / n_t
        m   = PHASE_META.get(ph, {})
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        lines.append(
            f"  [{m.get('group','?')}] {ph:22s}: {n_p:2d}/{n_t:2d} ({pct:5.1f}%)  {bar}  {m.get('label','')}"
        )

    lines += [
        "",
        "ChromaDB 학습·재활용 상세 분석",
        "-" * 80,
        f"  B1 (첫 요청):  web_search_tool 실행 = {b1_web_runs}/{len(b1_records)}",
        f"  B1 (첫 요청):  knowledge_writer 실행(학습 저장) = {b1_kw_runs}/{len(b1_records)}",
        f"  B2 (재요청):   visa_rag_search hit = {b2_rag_hit}/{len(b2_records)}",
        f"  B2 (재요청):   RAG only (웹검색 없음) = {b2_rag_only}/{len(b2_records)} ← 핵심 지표",
        "",
        f"  ChromaDB 재활용률: {100*b2_rag_only/max(len(b2_records),1):.1f}% "
        f"(목표: knowledge_writer 실행 수 이상)",
        "-" * 80,
        f"전체 신뢰도: {n_pass}/{total} ({overall:.1f}%)",
        "=" * 80,
    ]

    for ln in lines:
        print(ln)
        output_log.write(ln + "\n")

    return {
        "meta": {
            "timestamp":        datetime.now().isoformat(),
            "total":            total,
            "passed":           n_pass,
            "reliability_pct":  round(overall, 2),
        },
        "by_phase": {
            ph: {"total": len(v), "passed": sum(v), "pct": round(100*sum(v)/len(v), 2)}
            for ph, v in by_phase.items()
        },
        "chroma_analysis": {
            "b1_web_search_runs":    b1_web_runs,
            "b1_knowledge_writer_runs": b1_kw_runs,
            "b2_rag_hit":            b2_rag_hit,
            "b2_rag_only_no_web":    b2_rag_only,
            "chroma_reuse_pct":      round(100*b2_rag_only/max(len(b2_records),1), 2),
        },
        "records": records,
    }


if __name__ == "__main__":
    # API 헬스 체크
    try:
        resp = httpx.get(f"{API}/health", timeout=5)
        assert resp.status_code == 200
    except Exception as e:
        print(f"❌ API 미응답: {e}")
        sys.exit(1)

    started = time.time()
    header = (
        f"{'='*100}\n"
        f"VisaGuideAI ChromaDB 재검색 증명 + 개선 영역 검증 v50 "
        f"| {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"구성: Phase A (20개 개선 영역) + Phase B (30개 ChromaDB 검증)\n"
        f"{'='*100}\n"
    )
    print(header)

    # B1 케이스 분리 (B1 → 대기 → B2 순서 보장)
    phase_a1 = [(m,p,e,h,n) for m,p,e,h,n in ALL_50 if p == PH_A1]
    phase_a2 = [(m,p,e,h,n) for m,p,e,h,n in ALL_50 if p == PH_A2]
    phase_a3 = [(m,p,e,h,n) for m,p,e,h,n in ALL_50 if p == PH_A3]
    phase_b1 = [(m,p,e,h,n) for m,p,e,h,n in ALL_50 if p == PH_B1]
    phase_b2 = [(m,p,e,h,n) for m,p,e,h,n in ALL_50 if p == PH_B2]

    all_records = []

    with open(LOG_FILE, "w", encoding="utf-8") as log_fp:
        log_fp.write(header + "\n")

        all_records += run_phase(phase_a1, "Phase A1: Status Change 재검증", log_fp, 0)
        all_records += run_phase(phase_a2, "Phase A2: Multi-turn 재검증",    log_fp, 8)
        all_records += run_phase(phase_a3, "Phase A3: Conflicting 재검증",   log_fp, 14)
        all_records += run_phase(phase_b1, "Phase B1: ChromaDB 첫 저장",    log_fp, 20)

        # B1 실행 후 ChromaDB 반영 대기
        print(f"\n⏳ ChromaDB 반영 대기 {B1_B2_WAIT_SEC}초…")
        log_fp.write(f"\n⏳ ChromaDB 반영 대기 {B1_B2_WAIT_SEC}초…\n")
        time.sleep(B1_B2_WAIT_SEC)

        all_records += run_phase(phase_b2, "Phase B2: ChromaDB 재활용 증명", log_fp, 35)

        result = summarize(all_records, log_fp)
        log_fp.write(f"\n총 소요 시간: {int(time.time()-started)}초\n")

    with open(JSON_FILE, "w", encoding="utf-8") as jf:
        json.dump(result, jf, ensure_ascii=False, indent=2)

    print(f"\n📄 로그: {LOG_FILE}")
    print(f"📊 JSON: {JSON_FILE}")
    print(f"⏱️  소요: {int(time.time()-started)}초")
