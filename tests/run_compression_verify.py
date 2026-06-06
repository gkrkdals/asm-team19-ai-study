"""
후속질문 응답 압축 워크플로우 검증 — run_compression_verify
═══════════════════════════════════════════════════════════════════════════
검증 목표(요청 2·3):
  이전 대화가 현재 후속 요청과 관련될 때
    (1) 중복된 전체 템플릿이 아니라 '필요한 답변만' 제공하는가
    (2) '상위 대화를 참조'하는가
    (3) 반대로, 새로운 주제(국가 전환 등)에는 압축하지 않고 정상 추천하는가

판정 기준(턴별):
  - is_followup 플래그가 기대와 일치
  - 후속(compressed) 턴: 전체 템플릿(## 추천 비자/주요 자격 요건) 미출력 + 길이 대폭 감소 + 상위 참조 표현
  - 신규(full) 턴: 전체 템플릿 출력
═══════════════════════════════════════════════════════════════════════════
"""
import httpx, json, sys, time

API = "http://localhost:8000"

# 상위 대화 참조 표현(첫 문장 등)
REF_PHRASES = ["앞서", "앞선", "이전", "위에서", "말씀드린", "안내드린", "안내해 드린", "안내한"]
# 전체 추천 템플릿 시그니처
TEMPLATE_SIG = ["## 추천 비자", "## 주요 자격 요건", "## 필요 서류"]


def chat(message, history, sid="verify_compress"):
    route, acc = [], ""
    is_followup = is_visa = None
    with httpx.stream("POST", f"{API}/chat/stream",
                      json={"message": message, "session_id": sid, "history": history},
                      timeout=150) as r:
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
                            if t == "node": route.append(ev["node"])
                            elif t == "token": acc += ev.get("text", "")
                            elif t == "done":
                                acc = ev.get("final_response", acc)
                                is_followup = ev.get("is_followup")
                                is_visa = ev.get("is_visa_related")
                        except Exception:
                            pass
    return {"route": route, "answer": acc, "is_followup": is_followup, "is_visa": is_visa}


# (message, expected_followup, kind)  kind: "full" | "compressed"
SCENARIOS = [
    # 사용자가 제시한 예시 그대로 — 독일 블루카드 체인
    ("독일 블루카드 자격 요건을 알려주세요",          False, "full"),
    ("독일 블루카드 신청 시 필요한 서류는 무엇인가요?", True,  "compressed"),
    ("독일어 B1 미만일 때 대체 가능한 조건은 있나요?",  True,  "compressed"),
    ("블루카드 처리 기간은 보통 얼마나 걸리나요?",      True,  "compressed"),
    # 반대 사례: 새로운 국가로 전환 → 압축하지 말고 정상 추천(full)
    ("그럼 캐나다에서 취업하려면 어떤 비자가 필요한가요?", False, "full"),
    # 다시 후속 → 압축
    ("캐나다 그 비자 신청 시 필요한 서류는요?",         True,  "compressed"),
]


def judge(kind, ans):
    has_template = sum(1 for s in TEMPLATE_SIG if s in ans)
    has_ref = any(p in ans for p in REF_PHRASES)
    length = len(ans)
    if kind == "compressed":
        # 템플릿 미출력 + 상위 참조 표현
        ok = (has_template == 0) and has_ref
        detail = f"템플릿={has_template}개(기대0) 상위참조={'O' if has_ref else 'X'} 길이={length}"
    else:  # full
        ok = has_template >= 2
        detail = f"템플릿={has_template}개(기대≥2) 길이={length}"
    return ok, detail, length


def main():
    assert httpx.get(f"{API}/health", timeout=5).status_code == 200
    print("=" * 78)
    print("후속질문 응답 압축 워크플로우 검증")
    print("=" * 78)

    history = []
    rows = []
    full_len = None
    for i, (msg, exp_fu, kind) in enumerate(SCENARIOS, 1):
        res = chat(msg, history)
        ans = res["answer"] or ""
        fu_match = (bool(res["is_followup"]) == exp_fu)
        body_ok, detail, length = judge(kind, ans)
        if kind == "full" and "블루카드" in msg:
            full_len = length
        route = " → ".join(n.replace("intent_classifier", "intent")
                            .replace("visa_rag_search", "rag")
                            .replace("web_search_tool", "web")
                            .replace("response_formatter", "resp")
                            .replace("exception_handler", "exc") for n in res["route"])
        passed = fu_match and body_ok
        rows.append({"turn": i, "msg": msg, "kind": kind,
                     "exp_followup": exp_fu, "act_followup": res["is_followup"],
                     "fu_match": fu_match, "body_ok": body_ok,
                     "length": length, "route": res["route"], "passed": passed,
                     "answer_preview": ans[:200]})
        mark = "✅" if passed else "❌"
        print(f"\n[T{i}] {mark} ({kind}) {msg}")
        print(f"     route: {route}")
        print(f"     is_followup: 기대={exp_fu} 실측={res['is_followup']} {'✓' if fu_match else '✗ 불일치'}")
        print(f"     본문: {detail} → {'OK' if body_ok else '미달'}")
        history.append({"role": "user", "content": msg})
        history.append({"role": "assistant", "content": ans})
        time.sleep(0.8)

    # 압축률 계산(블루카드 full vs 첫 압축)
    comp_lens = [r["length"] for r in rows if r["kind"] == "compressed"]
    avg_comp = sum(comp_lens) / len(comp_lens) if comp_lens else 0
    reduction = (1 - avg_comp / full_len) * 100 if full_len else 0

    passed = sum(1 for r in rows if r["passed"])
    print("\n" + "=" * 78)
    print(f"종합: {passed}/{len(rows)} 통과")
    print(f"전체 템플릿 평균 길이: {full_len}자")
    print(f"압축 응답 평균 길이:   {avg_comp:.0f}자")
    print(f"평균 압축률:           {reduction:.1f}% 감소")
    print("=" * 78)

    out = {
        "summary": {
            "total": len(rows), "passed": passed,
            "full_len": full_len, "avg_compressed_len": round(avg_comp),
            "reduction_pct": round(reduction, 1),
        },
        "rows": rows,
    }
    import os
    p = os.path.join(os.path.dirname(__file__), "results_compression.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"📊 저장: {p}")

    # 검증 세션 정리
    try:
        httpx.delete(f"{API}/sessions/verify_compress", timeout=5)
    except Exception:
        pass

    sys.exit(0 if passed == len(rows) else 1)


if __name__ == "__main__":
    main()
