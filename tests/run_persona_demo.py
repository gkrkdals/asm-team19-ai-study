"""
페르소나 기반 시나리오 데모 — run_persona_demo.py
══════════════════════════════════════════════════════════════════════════
4가지 핵심 기능을 실제 API 호출로 검증:
  A. 신규 정보 → 웹검색 → ChromaDB RAG 저장
  B. 동일 국가 재질문 → RAG 즉답 (웹검색 생략)
  C. 후속질문 압축 응답 (is_followup=True → 라이트 카드)
  D. 예외 상황 처리 (status_change / cross_rule)

각 시나리오당 2개 케이스. 페르소나별 실제 대화 로그 + 내부 데이터 출력.
══════════════════════════════════════════════════════════════════════════
"""
import httpx, json, sys, time, textwrap, os

API = "http://localhost:8000"
WIDTH = 72

def hr(char="─"): print(char * WIDTH)
def h1(t): hr("═"); print(f"  {t}"); hr("═")
def h2(t): print(f"\n{'▌'} {t}"); hr("─")
def wrap(s, indent=4):
    return textwrap.fill(s, width=WIDTH - indent, initial_indent=" "*indent, subsequent_indent=" "*indent)


def chroma_count():
    """ChromaDB 현재 문서 수"""
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))
        from rag.vectorstore import get_collection
        return get_collection().count()
    except Exception:
        return "N/A"


def chat(message, history=None, sid="demo"):
    route, acc = [], ""
    slots = {}
    is_followup = is_visa = None
    kb_written = None

    with httpx.stream(
        "POST", f"{API}/chat/stream",
        json={"message": message, "session_id": sid, "history": history or []},
        timeout=120,
    ) as r:
        buf = ""
        for chunk in r.iter_text():
            buf += chunk
            while "\n\n" in buf:
                block, buf = buf.split("\n\n", 1)
                for line in block.split("\n"):
                    if not line.startswith("data:"): continue
                    try:
                        ev = json.loads(line[5:].strip())
                        t = ev.get("type")
                        if t == "node":
                            route.append(ev["node"])
                            if ev["node"] == "knowledge_writer":
                                # 이 노드가 실행됐다는 것 자체가 RAG 저장 발생
                                kb_written = True
                        elif t == "token":
                            acc += ev.get("text", "")
                        elif t == "slots":
                            slots.update(ev.get("slots") or {})
                        elif t == "meta":
                            if "is_followup" in ev: is_followup = ev["is_followup"]
                            if "is_visa_related" in ev: is_visa = ev["is_visa_related"]
                        elif t == "done":
                            acc = ev.get("final_response", acc)
                            if "is_followup" in ev: is_followup = ev["is_followup"]
                            if "is_visa_related" in ev: is_visa = ev["is_visa_related"]
                            s = ev.get("slots") or {}
                            if s: slots.update(s)
                    except Exception:
                        pass
    return {
        "route": route,
        "answer": acc,
        "slots": slots,
        "is_followup": is_followup,
        "is_visa": is_visa,
        "kb_written": kb_written or ("knowledge_writer" in route),
    }


def print_result(res, label=""):
    route_str = " → ".join(
        n.replace("intent_classifier","INTENT")
         .replace("visa_rag_search","RAG")
         .replace("web_search_tool","WEB")
         .replace("response_formatter","RESP")
         .replace("exception_handler","EXC")
         .replace("search_quality_gate","GATE")
         .replace("query_refiner","REFINE")
         .replace("knowledge_writer","KB✍")
         .replace("general_chat","CHAT")
        for n in res["route"]
    )
    print(f"\n  📍 경로: {route_str}")
    print(f"  🎯 슬롯: country={res['slots'].get('country')} | purpose={res['slots'].get('purpose')} | exception={res['slots'].get('exception_type')}")
    print(f"  🔖 플래그: is_followup={res['is_followup']} | is_visa={res['is_visa']} | RAG저장={res['kb_written']}")
    print(f"  📝 응답길이: {len(res['answer'])}자")
    print()
    # 응답 미리보기 (첫 400자)
    preview = res["answer"][:400].replace("\n", " ").strip()
    print(wrap(f'"{preview}..."' if len(res["answer"]) > 400 else f'"{preview}"'))


def cleanup(sid):
    try: httpx.delete(f"{API}/sessions/{sid}", timeout=5)
    except: pass


# ══════════════════════════════════════════════════════════════════════════
# TYPE A: 신규 국가 → 웹검색 → ChromaDB RAG 저장
# ══════════════════════════════════════════════════════════════════════════
def run_type_a():
    h1("TYPE A — 신규 정보 입수 시 ChromaDB RAG 자동 저장")
    print("  핵심 검증: 6개 기본국가 外 신규 국가 질의 시\n"
          "  웹검색(WEB) → 품질검증(GATE) → RAG저장(KB✍) 경로 확인\n"
          "  + 저장 후 재질의 시 RAG 직행(웹검색 생략) 확인\n")

    cases = [
        {
            "id": "A-1",
            "persona": "👩‍💻 이지수 (30, 프리랜서 개발자)",
            "background": "포르투갈 디지털 노마드 비자에 관심. 6개 기본국가 外 신규 국가.",
            "q1": "포르투갈에서 디지털 노마드로 1년 살면서 원격근무 하고 싶어요. 비자가 있나요?",
            "q2": "포르투갈 디지털 노마드 비자 소득 증명은 어떻게 하나요?",  # 재질의 → RAG
            "sid": "demo_a1",
        },
        {
            "id": "A-2",
            "persona": "👨‍🎓 김태호 (26, 대학원생)",
            "background": "핀란드 연구 장기체류 비자 희망. 신규 국가.",
            "q1": "핀란드에서 박사 연구를 위해 2년 체류하려면 어떤 비자가 필요한가요?",
            "q2": "핀란드 연구 비자 신청 서류는 어떻게 준비하나요?",  # 재질의 → RAG
            "sid": "demo_a2",
        },
    ]

    for c in cases:
        h2(f"[{c['id']}] {c['persona']}")
        print(f"  배경: {c['background']}")

        # ── Q1: 신규 국가 첫 질의 ──
        before = chroma_count()
        print(f"\n  ┌─ Q1 (첫 질의) ─ ChromaDB 현재 {before}개 문서")
        print(f"  │  사용자: \"{c['q1']}\"")
        r1 = chat(c["q1"], sid=c["sid"])
        after = chroma_count()
        print_result(r1)
        print(f"  📦 ChromaDB 변화: {before} → {after} ({'+'+str(after-before) if after!=before else '변화없음'})")

        # ── Q2: 동일 주제 재질의 → RAG 활용 ──
        time.sleep(1)
        history = [
            {"role": "user", "content": c["q1"]},
            {"role": "assistant", "content": r1["answer"][:200]},
        ]
        print(f"\n  ┌─ Q2 (동일 주제 재질의) ─ RAG 직답 기대")
        print(f"  │  사용자: \"{c['q2']}\"")
        r2 = chat(c["q2"], history=history, sid=c["sid"])
        print_result(r2)
        rag_hit = "RAG" in " → ".join(r2["route"]) and "WEB" not in " → ".join(r2["route"])
        print(f"  {'✅' if rag_hit else '⚠️'} {'RAG 직답 (웹검색 없음)' if rag_hit else 'RAG 없이 응답'}")

        cleanup(c["sid"])
        time.sleep(1)


# ══════════════════════════════════════════════════════════════════════════
# TYPE B: 기존 학습 데이터 → RAG 즉답 (웹검색 생략)
# ══════════════════════════════════════════════════════════════════════════
def run_type_b():
    h1("TYPE B — 이미 학습된 데이터는 RAG로 즉시 답변 (웹검색 생략)")
    print("  핵심 검증: 6개 기본국가(US/JP/GB/CA/AU/DE)에 대한 질의는\n"
          "  RAG 검색(RAG) 즉시 활용 → 웹검색(WEB) 불필요\n")

    cases = [
        {
            "id": "B-1",
            "persona": "👩‍⚕️ 박소연 (28, 간호사)",
            "background": "호주 간호사 취업비자. 기본 6개국 중 AU.",
            "q": "호주에서 간호사로 취업하고 싶어요. 어떤 비자가 필요한가요?",
            "sid": "demo_b1",
        },
        {
            "id": "B-2",
            "persona": "👨‍💼 최민준 (34, IT 컨설턴트)",
            "background": "미국 H-1B 취업비자. 기본 6개국 중 US.",
            "q": "미국에서 소프트웨어 엔지니어로 취업하고 싶어요. H-1B 비자 요건이 어떻게 되나요?",
            "sid": "demo_b2",
        },
    ]

    for c in cases:
        h2(f"[{c['id']}] {c['persona']}")
        print(f"  배경: {c['background']}")
        print(f"\n  사용자: \"{c['q']}\"")
        r = chat(c["q"], sid=c["sid"])
        print_result(r)
        route_str = " → ".join(r["route"])
        rag_only = "RAG" in route_str and "WEB" not in route_str
        web_used = "WEB" in route_str
        print(f"  {'✅' if rag_only else '⚠️'} {'RAG 즉답 — 웹검색 불필요' if rag_only else ('WEB 검색 발생(RAG 미스)' if web_used else '기타 경로')}")
        cleanup(c["sid"])
        time.sleep(1)


# ══════════════════════════════════════════════════════════════════════════
# TYPE C: 후속질문 압축 응답 (is_followup=True → 라이트 카드, 상위참조)
# ══════════════════════════════════════════════════════════════════════════
def run_type_c():
    h1("TYPE C — 후속질문 압축 응답 (이미 안내한 내용은 반복하지 않음)")
    print("  핵심 검증: T1 전체 안내 → T2·T3 후속질문 시\n"
          "  is_followup=True + 응답 대폭 압축 + '앞서 안내드린' 참조 표현\n")

    cases = [
        {
            "id": "C-1",
            "persona": "👩‍🏫 강유진 (25, 어학원 강사)",
            "background": "영국 학생비자. 영어 연수 후 장기체류 희망.",
            "turns": [
                ("영국에서 2년 어학연수를 하려면 어떤 비자가 필요한가요?", False),
                ("학생비자 신청에 필요한 영어 점수 기준이 어떻게 되나요?", True),
                ("영국 학생비자로 아르바이트도 할 수 있나요?", True),
            ],
            "sid": "demo_c1",
        },
        {
            "id": "C-2",
            "persona": "👨‍🔬 한재원 (31, 생명공학 연구원)",
            "background": "캐나다 Express Entry 영주권. 장기 정착 목표.",
            "turns": [
                ("캐나다에서 영주권을 받고 싶어요. Express Entry가 어떤 프로그램인가요?", False),
                ("CRS 점수를 높이는 방법이 있나요?", True),
                ("영주권 신청 후 처리 기간이 얼마나 걸리나요?", True),
            ],
            "sid": "demo_c2",
        },
    ]

    for c in cases:
        h2(f"[{c['id']}] {c['persona']}")
        print(f"  배경: {c['background']}\n")
        history = []
        prev_len = None

        for i, (q, expect_fu) in enumerate(c["turns"], 1):
            label = "T1 전체 안내" if i == 1 else f"T{i} 후속질문 {'(압축 기대)' if expect_fu else ''}"
            print(f"  ┌─ {label}")
            print(f"  │  사용자: \"{q}\"")
            r = chat(q, history=history, sid=c["sid"])
            ans_len = len(r["answer"])
            print_result(r)

            # 압축 여부 판정
            if expect_fu:
                ref_found = any(p in r["answer"] for p in ["앞서", "앞선", "이전", "안내드린", "말씀드린"])
                template_absent = "## 추천 비자" not in r["answer"]
                compressed = prev_len and (ans_len < prev_len * 0.8)
                print(f"  {'✅' if r['is_followup'] else '❌'} is_followup={'True' if r['is_followup'] else 'False'}")
                print(f"  {'✅' if ref_found else '⚠️'} 상위참조 표현: {'있음' if ref_found else '없음'}")
                print(f"  {'✅' if template_absent else '⚠️'} 전체 템플릿 생략: {'예' if template_absent else '아니오(반복됨)'}")
                print(f"  {'✅' if compressed else '⚠️'} 응답 압축: {prev_len}자 → {ans_len}자 ({int((1-ans_len/prev_len)*100) if prev_len else 0}% 감소)")
            else:
                print(f"  📄 T1 전체 응답: {ans_len}자")

            history.append({"role": "user", "content": q})
            history.append({"role": "assistant", "content": r["answer"][:300]})
            prev_len = ans_len
            time.sleep(0.5)
        cleanup(c["sid"])
        time.sleep(1)


# ══════════════════════════════════════════════════════════════════════════
# TYPE D: 예외 상황 처리 (status_change / cross_rule)
# ══════════════════════════════════════════════════════════════════════════
def run_type_d():
    h1("TYPE D — 예외 상황 전문 처리 (status_change / cross_rule)")
    print("  핵심 검증: 비자 전환·신분변경·난민·범죄기록 등 예외 요청 시\n"
          "  exception_handler 경로 정확 진입 + 전문 안내 제공\n")

    cases = [
        {
            "id": "D-1",
            "persona": "👩‍🏋️ 서아람 (27, 요가 강사)",
            "background": "호주 워킹홀리데이 중 취업 제의 받음 → 취업비자 전환 희망.",
            "q": "호주에서 워킹홀리데이 비자로 있는데, 요가 스튜디오에서 정식 취업 제안을 받았어요. 워킹홀리데이에서 취업비자로 바꾸고 싶은데 어떻게 해야 하나요?",
            "expected_exc": "status_change",
            "sid": "demo_d1",
        },
        {
            "id": "D-2",
            "persona": "🧑‍⚖️ 무함마드 아흐마드 (35, 전직 저널리스트)",
            "background": "본국 정치적 박해. 독일 난민 신청 절차 문의.",
            "q": "저는 고국에서 정치적 박해를 받아 독일로 왔어요. 난민 신청은 어떻게 해야 하나요? asylum 절차가 궁금합니다.",
            "expected_exc": "cross_rule",
            "sid": "demo_d2",
        },
    ]

    for c in cases:
        h2(f"[{c['id']}] {c['persona']}")
        print(f"  배경: {c['background']}")
        print(f"\n  사용자: \"{c['q']}\"")
        r = chat(c["q"], sid=c["sid"])
        print_result(r)
        exc_ok = (r["slots"].get("exception_type") == c["expected_exc"])
        route_ok = "EXC" in " → ".join(
            n.replace("exception_handler","EXC") for n in r["route"]
        )
        print(f"  {'✅' if exc_ok else '❌'} exception_type: 기대={c['expected_exc']}, 실측={r['slots'].get('exception_type')}")
        print(f"  {'✅' if route_ok else '❌'} exception_handler 경로 진입: {'예' if route_ok else '아니오'}")
        cleanup(c["sid"])
        time.sleep(1)


# ══════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    assert httpx.get(f"{API}/health", timeout=5).status_code == 200, "API not running"
    print()
    print("██╗   ██╗██╗███████╗ █████╗  ██████╗ ██╗   ██╗██╗██████╗ ███████╗")
    print("██║   ██║██║██╔════╝██╔══██╗██╔════╝ ██║   ██║██║██╔══██╗██╔════╝")
    print("██║   ██║██║███████╗███████║██║  ███╗██║   ██║██║██║  ██║█████╗  ")
    print("╚██╗ ██╔╝██║╚════██║██╔══██║██║   ██║██║   ██║██║██║  ██║██╔══╝  ")
    print(" ╚████╔╝ ██║███████║██║  ██║╚██████╔╝╚██████╔╝██║██████╔╝███████╗")
    print("  ╚═══╝  ╚═╝╚══════╝╚═╝  ╚═╝ ╚═════╝  ╚═════╝ ╚═╝╚═════╝ ╚══════╝")
    print()
    print("        페르소나 시나리오 데모 — 핵심 기능 4종 실증 검증")
    print()

    mode = sys.argv[1].upper() if len(sys.argv) > 1 else "ALL"
    if mode in ("A", "ALL"): run_type_a()
    if mode in ("B", "ALL"): run_type_b()
    if mode in ("C", "ALL"): run_type_c()
    if mode in ("D", "ALL"): run_type_d()

    print()
    hr("═")
    print("  ✅ 데모 완료")
    hr("═")
