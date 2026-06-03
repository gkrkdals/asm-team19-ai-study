"""
VisaGuideAI 180-scenario 검증 실행기
────────────────────────────────────
실행: python3 tests/run_v180.py
결과: tests/results_v180.json  +  tests/results_v180.log
────────────────────────────────────
"""
import json, httpx, time, sys, os
from collections import defaultdict
from datetime import datetime

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from tests.scenarios_v180 import ALL_180, CATEGORY_META

API = "http://localhost:8000"
LOG_FILE = os.path.join(os.path.dirname(__file__), "results_v180.log")
JSON_FILE = os.path.join(os.path.dirname(__file__), "results_v180.json")


def query_route(msg: str, sid: str, history=None, timeout: int = 90) -> list[str]:
    """단일 쿼리 실행 → 통과한 노드 목록 반환."""
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


def run_all(cases: list, output_log, verbose: bool = True) -> dict:
    """전체 케이스 실행 후 결과 dict 반환."""
    by_cat: dict[str, list] = defaultdict(list)  # cat → [(pass, route), ...]
    records = []
    started = time.time()

    header = (
        f"{'='*120}\n"
        f"VisaGuideAI 종합 검증 v180  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"총 케이스: {len(cases)} (기본 150 + 특수 30)\n"
        f"{'='*120}\n"
    )
    print(header)
    output_log.write(header + "\n")

    col_h = f"{'No':>3}  {'OK':2}  {'카테고리':15}  {'쿼리':50}  {'경로'}"
    print(col_h)
    output_log.write(col_h + "\n")
    print("-" * 120)
    output_log.write("-" * 120 + "\n")

    for i, (msg, cat, expects, history) in enumerate(cases, 1):
        t0 = time.time()
        route = query_route(msg, f"v180_{i:03d}", history)
        elapsed = time.time() - t0
        passed = any(n in route for n in expects)

        by_cat[cat].append(passed)
        records.append({
            "no": i, "msg": msg, "cat": cat,
            "expects": expects, "route": route,
            "passed": passed, "elapsed_s": round(elapsed, 1),
        })

        status = "✅" if passed else "❌"
        path = " → ".join(n.replace("_classifier","").replace("_search","")
                           .replace("_handler","").replace("_formatter","")
                           .replace("_tool","") for n in route[:4])
        line = f"{i:3d}  {status}  {cat:15}  {msg[:50]:50}  {path}"
        print(line)
        output_log.write(line + "\n")

        if i % 30 == 0:
            elapsed_total = time.time() - started
            rate = i / elapsed_total
            eta = int((len(cases) - i) / rate)
            prog = f"\n  ── [{i}/{len(cases)}] 경과 {int(elapsed_total)}s / 예상 잔여 {eta}s ──\n"
            print(prog)
            output_log.write(prog + "\n")

    # ── 결과 요약 ────────────────────────────────────────────────────────────
    total   = len(cases)
    n_pass  = sum(r["passed"] for r in records)
    overall = 100 * n_pass / total

    sep = "\n" + "=" * 120 + "\n"
    print(sep)
    output_log.write(sep)

    summary_lines = [
        "카테고리별 신뢰도 (개선 전 비교 포함)",
        "-" * 80,
    ]

    prev_scores = {   # 이전 124개 검증 대비 (확인용)
        "employment":  100.0, "study": 91.7, "extension": 73.3,
        "status_change": 80.0, "cross_rule": 90.0, "long_stay": 100.0,
        "deep_search": 25.0, "reaction": 100.0, "off_topic": 87.5,
        "new_country": 83.3, "multi_turn": 40.0, "conflicting": 20.0,
        "vague": 40.0, "edge_case": 60.0,
    }

    for cat in sorted(by_cat):
        results  = by_cat[cat]
        n_t      = len(results)
        n_p      = sum(results)
        pct      = 100 * n_p / n_t
        prev     = prev_scores.get(cat, 0)
        delta    = pct - prev
        arrow    = f"+{delta:.1f}%" if delta > 0 else (f"{delta:.1f}%" if delta < 0 else "±0%")
        meta     = CATEGORY_META.get(cat, {})
        line     = (f"  {meta.get('label','?'):18s} [{cat:15s}]"
                    f"  {n_p:3d}/{n_t:3d} ({pct:5.1f}%)"
                    f"  prev:{prev:5.1f}%  {arrow}")
        summary_lines.append(line)

    summary_lines += [
        "-" * 80,
        f"전체 신뢰도: {n_pass}/{total} ({overall:.1f}%)",
        f"소요 시간:   {int(time.time() - started)}초",
        "=" * 80,
    ]

    for line in summary_lines:
        print(line)
        output_log.write(line + "\n")

    return {
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "total": total, "passed": n_pass,
            "reliability_pct": round(overall, 2),
        },
        "by_category": {
            cat: {
                "total": len(v), "passed": sum(v),
                "pct": round(100 * sum(v) / len(v), 2),
            }
            for cat, v in by_cat.items()
        },
        "records": records,
    }


if __name__ == "__main__":
    # API 헬스 체크
    try:
        resp = httpx.get(f"{API}/health", timeout=5)
        assert resp.status_code == 200, f"API 응답 비정상: {resp.status_code}"
    except Exception as e:
        print(f"❌ API 미응답: {e}")
        sys.exit(1)

    with open(LOG_FILE, "w", encoding="utf-8") as log_fp:
        result = run_all(ALL_180, log_fp, verbose=True)

    with open(JSON_FILE, "w", encoding="utf-8") as jf:
        json.dump(result, jf, ensure_ascii=False, indent=2)

    print(f"\n📄 로그 저장: {LOG_FILE}")
    print(f"📊 JSON 저장: {JSON_FILE}")
