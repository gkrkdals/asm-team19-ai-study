"""
ChromaDB 재검색 증명 + 개선 영역 재검증 — v50
═══════════════════════════════════════════════════════════════════════════
구성
  Phase A (20개): v180 개선 필요 영역 재검증
    A1. status_change 재검증 (8개) — 화살표/전환 패턴
    A2. multi_turn    재검증 (6개) — 수정신호 + 맥락 리셋
    A3. conflicting   재검증 (6개) — 명시적 부정+목적 조합

  Phase B (30개): ChromaDB knowledge_writer 저장 → RAG 재활용 증명
    B1. 첫 요청  (15개): 신규 국가/최신 정보 → web_search_tool + knowledge_writer
    B2. 재요청   (15개): B1 이후 동일 국가 재요청 → visa_rag_search 만으로 처리

실행 순서: A → B1 → B2 (B2는 B1 실행 후에만 의미 있음)

형식: (msg, phase, category, expected_nodes, history, note)
  - expected_nodes: 이 중 하나라도 경로에 포함되면 PASS
  - note: 검증 의도 설명
═══════════════════════════════════════════════════════════════════════════
"""

# ─── Phase 상수 ────────────────────────────────────────────────────────────
PH_A1 = "A1_status_change"
PH_A2 = "A2_multi_turn"
PH_A3 = "A3_conflicting"
PH_B1 = "B1_first_request"
PH_B2 = "B2_chroma_recall"

# ══════════════════════════════════════════════════════════════════════════
# Phase A1 — status_change 재검증 (8개)
# 이전 신뢰도: 20% (3/15). 화살표 패턴 + 명시적 전환 키워드 보강 후 재확인.
# 기대 노드: exception_handler (상태변경은 예외 처리)
# ══════════════════════════════════════════════════════════════════════════
PHASE_A1 = [
    (
        "일본에서 관광비자로 입국 후 취업비자로 신분 변경이 가능한가요?",
        PH_A1, ["exception_handler"],
        None,
        "신분 변경 명시 + 관광→취업 패턴",
    ),
    (
        "호주 학생비자에서 워킹홀리데이 비자로 종류 변경 절차가 궁금해요",
        PH_A1, ["exception_handler"],
        None,
        "비자 종류 변경 명시",
    ),
    (
        "미국에서 관광비자를 취업비자로 전환하는 것이 가능한가요?",
        PH_A1, ["exception_handler"],
        None,
        "'전환' 키워드 명시",
    ),
    (
        "캐나다 관광 → 유학 비자 변경 절차를 알려주세요",
        PH_A1, ["exception_handler"],
        None,
        "화살표 패턴 직접 사용 (→)",
    ),
    (
        "취업비자에서 영주권으로 신분을 변경하는 절차가 어떻게 되나요?",
        PH_A1, ["exception_handler"],
        None,
        "취업→영주 전환 패턴",
    ),
    (
        "영국에서 학생비자 만료 후 취업비자로 신청 변경이 가능한가요?",
        PH_A1, ["exception_handler"],
        None,
        "학생→취업 + '신청 변경' 키워드",
    ),
    (
        "독일 비자 유형을 학생에서 취업으로 전환할 수 있나요?",
        PH_A1, ["exception_handler"],
        None,
        "학생→취업 + '전환' 키워드",
    ),
    (
        "호주 워킹홀리데이 후 영주권으로 신분 변경이 되나요?",
        PH_A1, ["exception_handler"],
        None,
        "워홀→영주권 신분 변경",
    ),
]

# ══════════════════════════════════════════════════════════════════════════
# Phase A2 — multi_turn 재검증 (6개)
# 이전 신뢰도: 42.9% (3/7). 수정신호 + 맥락 리셋 동작 확인.
# ══════════════════════════════════════════════════════════════════════════
PHASE_A2 = [
    (
        "아니 사실은 유학만 하고 싶어요",
        PH_A2, ["visa_rag_search"],
        [
            {"role": "user",      "content": "캐나다에서 취업하고 싶어요"},
            {"role": "assistant", "content": "캐나다 취업비자 안내입니다."},
        ],
        "수정신호(아니 사실은) → 유학으로 목적 변경",
    ),
    (
        "그런데 3개월만 더 머물고 싶어요",
        PH_A2, ["exception_handler"],
        [
            {"role": "user",      "content": "미국 관광비자로 입국했어요"},
            {"role": "assistant", "content": "미국 관광비자 정보입니다."},
        ],
        "이전 맥락(미국 관광) 유지 + 체류 연장 요청",
    ),
    (
        "다시 생각해보니 취업보다 유학이 맞는 것 같아요",
        PH_A2, ["visa_rag_search"],
        [
            {"role": "user",      "content": "캐나다 취업 비자에 관심 있어요"},
            {"role": "assistant", "content": "취업비자 안내입니다."},
        ],
        "수정신호(다시 생각해보니) → 유학으로 전환",
    ),
    (
        "그럼 영국 학생비자는 어떤가요?",
        PH_A2, ["visa_rag_search"],
        [
            {"role": "user",      "content": "미국 유학 비자 알려줘"},
            {"role": "assistant", "content": "미국 F1 비자 정보입니다."},
        ],
        "국가 변경(미국→영국) + 목적(유학) 유지",
    ),
    (
        "미안해요, 사실 일자리를 구하고 싶어요",
        PH_A2, ["visa_rag_search"],
        [
            {"role": "user",      "content": "유학에 관심이 있어요"},
            {"role": "assistant", "content": "유학비자 정보입니다."},
        ],
        "수정신호(미안해요 사실) → 취업으로 목적 변경",
    ),
    (
        "사실은 장기 거주가 목적이에요",
        PH_A2, ["visa_rag_search"],
        [
            {"role": "user",      "content": "단기 여행으로 가려고요"},
            {"role": "assistant", "content": "단기 여행 비자 정보입니다."},
        ],
        "수정신호(사실은) → 장기 거주로 목적 변경",
    ),
]

# ══════════════════════════════════════════════════════════════════════════
# Phase A3 — conflicting 재검증 (6개)
# 이전 신뢰도: 50% (4/8). 명시적 부정+목적 패턴 처리 재확인.
# ══════════════════════════════════════════════════════════════════════════
PHASE_A3 = [
    (
        "관광이 아니라 취업으로 가고 싶어요",
        PH_A3, ["exception_handler", "visa_rag_search"],
        None,
        "'이 아니라' 부정 + 취업 목적 조합",
    ),
    (
        "유학이 아니라 취업비자가 필요해요",
        PH_A3, ["exception_handler", "visa_rag_search"],
        None,
        "'이 아니라' + 취업비자 명시",
    ),
    (
        "워킹홀리데이가 아닌 정규 취업비자를 원해요",
        PH_A3, ["visa_rag_search"],
        None,
        "'이 아닌' + 정규 취업비자 명시",
    ),
    (
        "미국에서 관광비자로 입국하지만 실제로는 취업을 원해요",
        PH_A3, ["exception_handler"],
        None,
        "관광→취업 상충 (신분변경 케이스)",
    ),
    (
        "단기 체류가 아니라 장기 거주를 원해요",
        PH_A3, ["visa_rag_search"],
        None,
        "단기→장기 상충 → 장기 거주 목적 우선",
    ),
    (
        "여행이 아니라 이민을 생각하고 있어요",
        PH_A3, ["visa_rag_search"],
        None,
        "여행→이민 상충 → 이민 목적 우선",
    ),
]

# ══════════════════════════════════════════════════════════════════════════
# Phase B1 — 첫 요청: ChromaDB 미보유 국가/주제 → 웹검색 후 학습 저장 (15개)
#
# 기대 경로: intent → web_search_tool → search_quality_gate → knowledge_writer → response
# PASS 조건: web_search_tool 또는 knowledge_writer 가 경로에 포함됨
# NOTE: knowledge_writer는 search_quality="good" 일 때만 실행됨
#       → web_search_tool 만 나타나도 PASS (quality gate 판단은 런타임)
# ══════════════════════════════════════════════════════════════════════════
PHASE_B1 = [
    (
        "포르투갈 골든비자 취득 조건은 무엇인가요?",
        PH_B1, ["web_search_tool", "knowledge_writer"],
        None,
        "신규 국가(PT) 첫 요청 → 웹검색 후 ChromaDB 저장",
    ),
    (
        "스페인에서 디지털 노마드 비자를 받고 싶어요",
        PH_B1, ["web_search_tool", "knowledge_writer"],
        None,
        "신규 국가(ES) 첫 요청 → 웹검색 후 ChromaDB 저장",
    ),
    (
        "아랍에미리트(UAE) 취업비자 요건은 어떻게 되나요?",
        PH_B1, ["web_search_tool", "knowledge_writer"],
        None,
        "신규 국가(AE) 첫 요청 → 웹검색 후 ChromaDB 저장",
    ),
    (
        "말레이시아 MM2H 비자로 장기 거주가 가능한가요?",
        PH_B1, ["web_search_tool", "knowledge_writer"],
        None,
        "신규 국가(MY) 첫 요청 → 웹검색 후 ChromaDB 저장",
    ),
    (
        "태국 LTR(장기 거주) 비자 조건을 알려주세요",
        PH_B1, ["web_search_tool", "knowledge_writer"],
        None,
        "신규 국가(TH) 첫 요청 → 웹검색 후 ChromaDB 저장",
    ),
    (
        "이탈리아 취업비자 신청 절차가 궁금해요",
        PH_B1, ["web_search_tool", "knowledge_writer"],
        None,
        "신규 국가(IT) 첫 요청 → 웹검색 후 ChromaDB 저장",
    ),
    (
        "네덜란드 고숙련 이민자 비자(HSM) 조건은?",
        PH_B1, ["web_search_tool", "knowledge_writer"],
        None,
        "신규 국가(NL) 첫 요청 → 웹검색 후 ChromaDB 저장",
    ),
    (
        "스웨덴 취업비자 신청 방법을 알려주세요",
        PH_B1, ["web_search_tool", "knowledge_writer"],
        None,
        "신규 국가(SE) 첫 요청 → 웹검색 후 ChromaDB 저장",
    ),
    (
        "덴마크 그린카드 비자로 일할 수 있나요?",
        PH_B1, ["web_search_tool", "knowledge_writer"],
        None,
        "신규 국가(DK) 첫 요청 → 웹검색 후 ChromaDB 저장",
    ),
    (
        "노르웨이에서 취업비자를 받으려면 어떻게 해야 하나요?",
        PH_B1, ["web_search_tool", "knowledge_writer"],
        None,
        "신규 국가(NO) 첫 요청 → 웹검색 후 ChromaDB 저장",
    ),
    (
        "아일랜드 취업허가증(Employment Permit) 종류와 조건은?",
        PH_B1, ["web_search_tool", "knowledge_writer"],
        None,
        "신규 국가(IE) 첫 요청 → 웹검색 후 ChromaDB 저장",
    ),
    (
        "핀란드에서 일하려면 어떤 비자가 필요한가요?",
        PH_B1, ["web_search_tool", "knowledge_writer"],
        None,
        "신규 국가(FI) 첫 요청 → 웹검색 후 ChromaDB 저장",
    ),
    (
        "남아공 취업비자(Work Permit) 신청 조건을 알려주세요",
        PH_B1, ["web_search_tool", "knowledge_writer"],
        None,
        "신규 국가(ZA) 첫 요청 → 웹검색 후 ChromaDB 저장",
    ),
    (
        "브라질 디지털 노마드 비자 조건은 무엇인가요?",
        PH_B1, ["web_search_tool", "knowledge_writer"],
        None,
        "신규 국가(BR) 첫 요청 → 웹검색 후 ChromaDB 저장",
    ),
    (
        "인도 취업비자(Employment Visa) 신청 자격을 알려주세요",
        PH_B1, ["web_search_tool", "knowledge_writer"],
        None,
        "신규 국가(IN) 첫 요청 → 웹검색 후 ChromaDB 저장",
    ),
]

# ══════════════════════════════════════════════════════════════════════════
# Phase B2 — 재요청: B1 실행 후 ChromaDB에서 직접 추출해야 함 (15개)
#
# B1에서 knowledge_writer가 ChromaDB에 저장한 국가 정보를
# 재요청 시 visa_rag_search(RAG)로 가져와야 함 → 웹검색 불필요
#
# 기대 경로: intent → visa_rag_search → response (web_search_tool 없음!)
# PASS 조건: visa_rag_search 가 경로에 포함됨 (web_search_tool 미포함이 이상적)
#
# NOTE: ChromaDB 저장 여부는 search_quality="good" 판단에 달림.
#       저장이 안 된 경우 web_search_tool 이 다시 실행될 수 있음 → 허용 PASS.
#       핵심 검증 포인트: "같은 국가 재요청 시 RAG hit가 발생하는가?"
# ══════════════════════════════════════════════════════════════════════════
PHASE_B2 = [
    (
        "포르투갈 골든비자 자격 요건 다시 알려줘",
        PH_B2, ["visa_rag_search"],
        None,
        "PT 재요청 → ChromaDB 학습 문서에서 직접 추출",
    ),
    (
        "스페인 디지털 노마드 비자 신청 방법이 어떻게 되죠?",
        PH_B2, ["visa_rag_search"],
        None,
        "ES 재요청 → ChromaDB 학습 문서에서 직접 추출",
    ),
    (
        "UAE에서 취업비자 받는 조건 한번 더 알려줘요",
        PH_B2, ["visa_rag_search"],
        None,
        "AE 재요청 → ChromaDB 학습 문서에서 직접 추출",
    ),
    (
        "말레이시아 MM2H 비자 신청 자격 조건이 뭔가요?",
        PH_B2, ["visa_rag_search"],
        None,
        "MY 재요청 → ChromaDB 학습 문서에서 직접 추출",
    ),
    (
        "태국에서 장기 거주 비자 받으려면 어떻게 하나요?",
        PH_B2, ["visa_rag_search"],
        None,
        "TH 재요청 → ChromaDB 학습 문서에서 직접 추출",
    ),
    (
        "이탈리아 취업비자 절차를 간략히 설명해줘",
        PH_B2, ["visa_rag_search"],
        None,
        "IT 재요청 → ChromaDB 학습 문서에서 직접 추출",
    ),
    (
        "네덜란드 고숙련 비자 조건이 어떻게 되나요?",
        PH_B2, ["visa_rag_search"],
        None,
        "NL 재요청 → ChromaDB 학습 문서에서 직접 추출",
    ),
    (
        "스웨덴 취업비자 조건 요약해줘",
        PH_B2, ["visa_rag_search"],
        None,
        "SE 재요청 → ChromaDB 학습 문서에서 직접 추출",
    ),
    (
        "덴마크 취업비자로 일할 수 있는 조건 알려줘",
        PH_B2, ["visa_rag_search"],
        None,
        "DK 재요청 → ChromaDB 학습 문서에서 직접 추출",
    ),
    (
        "노르웨이 취업비자 신청 요건이 어떻게 되나요?",
        PH_B2, ["visa_rag_search"],
        None,
        "NO 재요청 → ChromaDB 학습 문서에서 직접 추출",
    ),
    (
        "아일랜드 취업허가증 종류와 신청 조건은?",
        PH_B2, ["visa_rag_search"],
        None,
        "IE 재요청 → ChromaDB 학습 문서에서 직접 추출",
    ),
    (
        "핀란드 취업비자 신청 조건 다시 알려줘",
        PH_B2, ["visa_rag_search"],
        None,
        "FI 재요청 → ChromaDB 학습 문서에서 직접 추출",
    ),
    (
        "남아공 취업비자 신청 자격이 어떻게 되나요?",
        PH_B2, ["visa_rag_search"],
        None,
        "ZA 재요청 → ChromaDB 학습 문서에서 직접 추출",
    ),
    (
        "브라질에서 디지털 노마드 비자 받으려면?",
        PH_B2, ["visa_rag_search"],
        None,
        "BR 재요청 → ChromaDB 학습 문서에서 직접 추출",
    ),
    (
        "인도 취업비자 자격 요건을 알려주세요",
        PH_B2, ["visa_rag_search"],
        None,
        "IN 재요청 → ChromaDB 학습 문서에서 직접 추출",
    ),
]

# ── 전체 50개 (실행 순서 보장: A → B1 → B2) ──────────────────────────────
ALL_50 = PHASE_A1 + PHASE_A2 + PHASE_A3 + PHASE_B1 + PHASE_B2

assert len(ALL_50)    == 50, f"전체 수 오류: {len(ALL_50)}"
assert len(PHASE_A1)  ==  8
assert len(PHASE_A2)  ==  6
assert len(PHASE_A3)  ==  6
assert len(PHASE_B1)  == 15
assert len(PHASE_B2)  == 15

# ── 메타 ─────────────────────────────────────────────────────────────────
PHASE_META = {
    PH_A1: {"label": "Status Change 재검증",            "count": 8,  "group": "A"},
    PH_A2: {"label": "Multi-turn 재검증",               "count": 6,  "group": "A"},
    PH_A3: {"label": "Conflicting 재검증",              "count": 6,  "group": "A"},
    PH_B1: {"label": "ChromaDB 첫 저장(웹검색)",         "count": 15, "group": "B"},
    PH_B2: {"label": "ChromaDB 재활용(RAG 재검색 증명)", "count": 15, "group": "B"},
}

if __name__ == "__main__":
    from collections import Counter
    ph_counts = Counter(ph for _, ph, _, _, _ in ALL_50)
    print(f"총 케이스: {len(ALL_50)}")
    print("\nPhase별 케이스 수:")
    for ph, cnt in sorted(ph_counts.items()):
        m = PHASE_META.get(ph, {})
        print(f"  [{m.get('group','?')}] {ph:22s}: {cnt:2d}개  ({m.get('label','')})")
