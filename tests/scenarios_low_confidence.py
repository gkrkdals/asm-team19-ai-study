"""
저신뢰 영역 검증 시나리오 — Round 12
══════════════════════════════════════════════════════════════════════════
v70(R11) 검증에서 신뢰도가 낮거나 미검증으로 분류된 4개 영역:

  Group 1 (G1_SC) : status_change — 동사형 자연어 전환 표현 (12개)
  Group 2 (G2_EXC): G2_EXC 기타 예외 — 난민/망명/간접 범죄 기록 (10개)
  Group 3 (G3_DT) : 후반 대화(T7+) — 깊은 턴에서 컨텍스트 유지 (13개)
  Group 4 (G4_FU) : 압축 워크플로우 — is_followup 오감지 엣지케이스 (10개)

  총 45개 시나리오

판정 기준:
  expected_route  : 경로에 반드시 포함되어야 할 노드명 목록 (순서 무관)
  forbidden_route : 경로에 포함되면 안 되는 노드명 목록
  check_followup  : None(검사 안 함) | True | False — is_followup 기대값
  check_exception : 기대 exception_type("status_change"|"rejection"|"cross_rule"|None)
  check_country   : 기대 country 코드(None = 검사 안 함)
══════════════════════════════════════════════════════════════════════════
"""

# ──────────────────────────────────────────────────────────────────────
# Group 1 — status_change: 동사형 자연어 전환 표현
# 목표: exception_handler 경로 + exception_type == "status_change"
# ──────────────────────────────────────────────────────────────────────
G1_STATUS_CHANGE = [
    {
        "id": "G1-01",
        "description": "동사형 전환 + 명시적 국가",
        "messages": [
            {"role": "user", "content": "미국에서 학생비자를 취업비자로 바꾸고 싶어요. 어떻게 해야 하나요?"}
        ],
        "expected_route": ["intent_classifier", "exception_handler"],
        "forbidden_route": [],
        "check_followup": False,
        "check_exception": "status_change",
        "check_country": "US",
    },
    {
        "id": "G1-02",
        "description": "동사형 전환 + 국가 없음 (컨텍스트에서 추론 불가)",
        "messages": [
            {"role": "user", "content": "학생비자를 취업비자로 바꾸고 싶은데 어떻게 해요?"}
        ],
        "expected_route": ["intent_classifier", "exception_handler"],
        "forbidden_route": [],
        "check_followup": False,
        "check_exception": "status_change",
        "check_country": None,  # 국가 없어도 status_change 감지 여부가 핵심
    },
    {
        "id": "G1-03",
        "description": "'갈아타다' 표현",
        "messages": [
            {"role": "user", "content": "캐나다에서 관광비자에서 취업비자로 갈아타고 싶어요"}
        ],
        "expected_route": ["intent_classifier", "exception_handler"],
        "forbidden_route": [],
        "check_followup": False,
        "check_exception": "status_change",
        "check_country": "CA",
    },
    {
        "id": "G1-04",
        "description": "'조정하다' 표현",
        "messages": [
            {"role": "user", "content": "독일에서 현재 비자 유형을 조정하려면 어떻게 해야 하나요?"}
        ],
        "expected_route": ["intent_classifier", "exception_handler"],
        "forbidden_route": [],
        "check_followup": False,
        "check_exception": "status_change",
        "check_country": "DE",
    },
    {
        "id": "G1-05",
        "description": "화살표 없이 '~에서 ~로' 문장형",
        "messages": [
            {"role": "user", "content": "호주 워킹홀리데이에서 취업비자로 전환하고 싶어요"}
        ],
        "expected_route": ["intent_classifier", "exception_handler"],
        "forbidden_route": [],
        "check_followup": False,
        "check_exception": "status_change",
        "check_country": "AU",
    },
    {
        "id": "G1-06",
        "description": "화살표 패턴 (기존 동작 유지 확인)",
        "messages": [
            {"role": "user", "content": "학생 → 취업으로 비자 전환 어떻게 하나요?"}
        ],
        "expected_route": ["intent_classifier", "exception_handler"],
        "forbidden_route": [],
        "check_followup": False,
        "check_exception": "status_change",
        "check_country": None,
    },
    {
        "id": "G1-07",
        "description": "국가 맥락이 이전 턴에만 있는 암묵적 전환 요청",
        "messages": [
            {"role": "user",      "content": "일본에서 취업비자에 대해 알고 싶어요"},
            {"role": "assistant", "content": "일본 취업비자(취로비자)는..."},
            {"role": "user",      "content": "그럼 유학비자에서 이걸로 바꾸고 싶은데 어떻게 해요?"}
        ],
        "expected_route": ["intent_classifier", "exception_handler"],
        "forbidden_route": [],
        "check_followup": False,       # 같은 국가지만 status_change → followup 아님
        "check_exception": "status_change",
        "check_country": "JP",
    },
    {
        "id": "G1-08",
        "description": "부분 표현 — '종류를 바꾸'",
        "messages": [
            {"role": "user", "content": "영국에서 비자 종류를 바꾸려면 어떤 절차가 필요한가요?"}
        ],
        "expected_route": ["intent_classifier", "exception_handler"],
        "forbidden_route": [],
        "check_followup": False,
        "check_exception": "status_change",
        "check_country": "GB",
    },
    {
        "id": "G1-09",
        "description": "FP 방지 — 단순 취업비자 질문 (전환 아님)",
        "messages": [
            {"role": "user", "content": "미국에서 취업비자를 받으려면 어떻게 하나요?"}
        ],
        "expected_route": ["intent_classifier"],
        "forbidden_route": [],         # exception_handler 가 없어야 하는 건 아님(FP 체크 목적)
        "check_followup": False,
        "check_exception": None,       # status_change가 아니어야 함 (None이면 FP)
        "check_country": "US",
    },
    {
        "id": "G1-10",
        "description": "FP 방지 — '취업 전환 가능한가요?' (너무 광범위한 표현)",
        "messages": [
            {"role": "user", "content": "캐나다 워킹홀리데이 후 취업 전환이 가능한가요?"}
        ],
        "expected_route": ["intent_classifier", "exception_handler"],
        "forbidden_route": [],
        "check_followup": False,
        "check_exception": "status_change",
        "check_country": "CA",
    },
    {
        "id": "G1-11",
        "description": "'유형을 바꿔' 표현",
        "messages": [
            {"role": "user", "content": "지금 비자 유형을 바꿔서 계속 있을 수 있나요? 독일입니다."}
        ],
        "expected_route": ["intent_classifier", "exception_handler"],
        "forbidden_route": [],
        "check_followup": False,
        "check_exception": "status_change",
        "check_country": "DE",
    },
    {
        "id": "G1-12",
        "description": "비자 업그레이드 표현 (기존 동작 유지)",
        "messages": [
            {"role": "user", "content": "미국 관광비자에서 취업비자로 업그레이드 하고 싶어요"}
        ],
        "expected_route": ["intent_classifier", "exception_handler"],
        "forbidden_route": [],
        "check_followup": False,
        "check_exception": "status_change",
        "check_country": "US",
    },
]

# ──────────────────────────────────────────────────────────────────────
# Group 2 — G2_EXC 기타 예외: 난민·망명·간접 범죄 표현
# 목표: exception_handler + is_visa_related=True
# ──────────────────────────────────────────────────────────────────────
G2_EXCEPTION_OTHER = [
    {
        "id": "G2-01",
        "description": "난민 신청 직접 표현",
        "messages": [
            {"role": "user", "content": "독일에서 난민 신청은 어떻게 하나요?"}
        ],
        "expected_route": ["intent_classifier", "exception_handler"],
        "forbidden_route": [],
        "check_followup": False,
        "check_exception": "cross_rule",
        "check_country": "DE",
    },
    {
        "id": "G2-02",
        "description": "정치적 망명 표현",
        "messages": [
            {"role": "user", "content": "정치적 망명 절차에 대해 알고 싶어요"}
        ],
        "expected_route": ["intent_classifier", "exception_handler"],
        "forbidden_route": [],
        "check_followup": False,
        "check_exception": "cross_rule",
        "check_country": None,
    },
    {
        "id": "G2-03",
        "description": "asylum 영어 표현",
        "messages": [
            {"role": "user", "content": "영국에서 asylum 신청 자격이 궁금해요"}
        ],
        "expected_route": ["intent_classifier", "exception_handler"],
        "forbidden_route": [],
        "check_followup": False,
        "check_exception": "cross_rule",
        "check_country": "GB",
    },
    {
        "id": "G2-04",
        "description": "간접 범죄 기록 표현 (경범죄)",
        "messages": [
            {"role": "user", "content": "예전에 경범죄가 있는데 캐나다 비자 신청 가능한가요?"}
        ],
        "expected_route": ["intent_classifier", "exception_handler"],
        "forbidden_route": [],
        "check_followup": False,
        "check_exception": "cross_rule",
        "check_country": "CA",
    },
    {
        "id": "G2-05",
        "description": "간접 표현 — '기록이 있는데'",
        "messages": [
            {"role": "user", "content": "과거에 범죄 기록이 있는데 미국 비자 받을 수 있나요?"}
        ],
        "expected_route": ["intent_classifier", "exception_handler"],
        "forbidden_route": [],
        "check_followup": False,
        "check_exception": "cross_rule",
        "check_country": "US",
    },
    {
        "id": "G2-06",
        "description": "'전과' 키워드 (기존 동작 유지)",
        "messages": [
            {"role": "user", "content": "전과가 있어도 호주 비자 신청이 가능한가요?"}
        ],
        "expected_route": ["intent_classifier", "exception_handler"],
        "forbidden_route": [],
        "check_followup": False,
        "check_exception": "cross_rule",
        "check_country": "AU",
    },
    {
        "id": "G2-07",
        "description": "난민 + 국가 없음",
        "messages": [
            {"role": "user", "content": "난민 인정을 받으려면 어떤 절차를 밟아야 하나요?"}
        ],
        "expected_route": ["intent_classifier", "exception_handler"],
        "forbidden_route": [],
        "check_followup": False,
        "check_exception": "cross_rule",
        "check_country": None,
    },
    {
        "id": "G2-08",
        "description": "보호 신청 표현",
        "messages": [
            {"role": "user", "content": "독일에서 인도적 보호 신청이 가능한지 알고 싶어요"}
        ],
        "expected_route": ["intent_classifier", "exception_handler"],
        "forbidden_route": [],
        "check_followup": False,
        "check_exception": "cross_rule",
        "check_country": "DE",
    },
    {
        "id": "G2-09",
        "description": "FP 방지 — 일반 취업 질문 (범죄 없음)",
        "messages": [
            {"role": "user", "content": "캐나다 취업비자 요건이 어떻게 되나요?"}
        ],
        "expected_route": ["intent_classifier"],
        "forbidden_route": [],
        "check_followup": False,
        "check_exception": None,    # cross_rule이 아니어야 함
        "check_country": "CA",
    },
    {
        "id": "G2-10",
        "description": "FP 방지 — '기록' 단어가 포함된 비관련 질문",
        "messages": [
            {"role": "user", "content": "비자 신청 기록이 남나요? 미국 비자요."}
        ],
        "expected_route": ["intent_classifier"],
        "forbidden_route": [],
        "check_followup": False,
        "check_exception": None,    # 단순 기록 조회 질문 → cross_rule 아님
        "check_country": "US",
    },
]

# ──────────────────────────────────────────────────────────────────────
# Group 3 — 후반 대화 T7+: 깊은 턴에서 컨텍스트 유지
# 독일 블루카드 10턴 체인 기준
# 목표: T7+ 에서도 country=DE 유지, 적절한 is_followup 판정
# ──────────────────────────────────────────────────────────────────────
_DE_BLUECARD_HISTORY = [
    # T1: 전체 안내
    {"role": "user",      "content": "독일 블루카드 자격 요건을 알려주세요"},
    {"role": "assistant", "content": "독일 블루카드는 고급 취업비자로, 학사 이상 학위와 최저 연봉 기준(약 58,400 EUR)이 필요합니다.\n## 추천 비자\n## 주요 자격 요건\n## 필요 서류"},
    # T2: 후속
    {"role": "user",      "content": "필요 서류는 무엇인가요?"},
    {"role": "assistant", "content": "앞서 안내드린 독일 블루카드 기준으로 말씀드리면, 여권·학위증·고용계약서가 필요합니다."},
    # T3: 후속
    {"role": "user",      "content": "독일어 B1 미만이면 대체 가능한가요?"},
    {"role": "assistant", "content": "앞서 안내드린 기준으로, STEM 분야이면 더 낮은 연봉 기준(약 45,552 EUR)이 적용됩니다."},
    # T4: 후속
    {"role": "user",      "content": "처리 기간은 얼마나 걸리나요?"},
    {"role": "assistant", "content": "앞서 안내드린 독일 블루카드의 경우 보통 4~12주가 소요됩니다."},
    # T5: 후속
    {"role": "user",      "content": "배우자 비자는 같이 신청할 수 있나요?"},
    {"role": "assistant", "content": "앞서 안내드린 독일 블루카드 기준으로, 배우자와 미성년 자녀는 가족 재결합 비자로 동반 신청이 가능합니다."},
    # T6: 후속
    {"role": "user",      "content": "블루카드 갱신 조건은 어떻게 되나요?"},
    {"role": "assistant", "content": "앞서 안내드린 독일 블루카드는 최초 4년 발급 후 영주권으로 이어지는 경로가 있습니다."},
]

G3_DEEP_TURNS = [
    # T7: 후속 질문 — is_followup=True, country=DE 유지
    {
        "id": "G3-01",
        "description": "T7 일반 후속 질문 — country=DE + is_followup=True",
        "messages": _DE_BLUECARD_HISTORY + [
            {"role": "user", "content": "블루카드로 독일 영주권 신청 기간이 얼마나 걸리나요?"}
        ],
        "expected_route": ["intent_classifier", "response_formatter"],
        "forbidden_route": [],
        "check_followup": True,
        "check_exception": None,
        "check_country": "DE",
    },
    # T7: 거절 키워드 → exception_handler (올바른 동작)
    {
        "id": "G3-02",
        "description": "T7 '거절' 키워드 → exception_handler, country=DE 유지",
        "messages": _DE_BLUECARD_HISTORY + [
            {"role": "user", "content": "블루카드 신청이 거절됐을 때 어떻게 해야 하나요?"}
        ],
        "expected_route": ["intent_classifier", "exception_handler"],
        "forbidden_route": [],
        "check_followup": False,        # 예외 처리 → followup 아님
        "check_exception": "rejection",
        "check_country": "DE",
    },
    # T7: 연장 키워드 → exception_handler
    {
        "id": "G3-03",
        "description": "T7 '연장' 키워드 → exception_handler, country=DE 유지",
        "messages": _DE_BLUECARD_HISTORY + [
            {"role": "user", "content": "블루카드 만료 전 연장 신청은 언제부터 가능한가요?"}
        ],
        "expected_route": ["intent_classifier", "exception_handler"],
        "forbidden_route": [],
        "check_followup": False,
        "check_exception": "extension",
        "check_country": "DE",
    },
    # T8: 예외 후 재후속 (국가 유지 + 후속 압축)
    {
        "id": "G3-04",
        "description": "T8 예외 처리 후 일반 후속 — is_followup=True 복귀",
        "messages": _DE_BLUECARD_HISTORY + [
            {"role": "user",      "content": "블루카드 신청이 거절됐을 때 어떻게 해야 하나요?"},
            {"role": "assistant", "content": "블루카드 거절 시 행정법원 이의 신청 또는 조건 개선 후 재신청이 가능합니다."},
            {"role": "user",      "content": "이의 신청 기간은 얼마나 되나요?"}
        ],
        "expected_route": ["intent_classifier", "response_formatter"],
        "forbidden_route": [],
        "check_followup": True,
        "check_exception": None,
        "check_country": "DE",
    },
    # T7: 국가 전환 → 새 국가 반영, is_followup=False
    {
        "id": "G3-05",
        "description": "T7 국가 전환 → country 교체, is_followup=False",
        "messages": _DE_BLUECARD_HISTORY + [
            {"role": "user", "content": "그럼 캐나다 취업비자는 어떻게 되나요?"}
        ],
        "expected_route": ["intent_classifier"],
        "forbidden_route": [],
        "check_followup": False,
        "check_exception": None,
        "check_country": "CA",
    },
    # T8: 국가 전환 후 후속 → 새 국가 기준 is_followup=True
    {
        "id": "G3-06",
        "description": "T8 국가 전환 후 후속 → 새 국가 기준 압축",
        "messages": _DE_BLUECARD_HISTORY + [
            {"role": "user",      "content": "그럼 캐나다 취업비자는 어떻게 되나요?"},
            {"role": "assistant", "content": "캐나다 취업비자(LMIA 기반)는 고용주의 노동시장영향평가가 필요합니다.\n## 추천 비자\n## 주요 자격 요건"},
            {"role": "user",      "content": "LMIA 없이 취업비자 받는 방법도 있나요?"}
        ],
        "expected_route": ["intent_classifier", "response_formatter"],
        "forbidden_route": [],
        "check_followup": True,
        "check_exception": None,
        "check_country": "CA",
    },
    # T9: 매우 깊은 후속 — 국가 컨텍스트 유지 여부
    {
        "id": "G3-07",
        "description": "T9 비자 취소/철회 질문 — country=DE 유지",
        "messages": _DE_BLUECARD_HISTORY + [
            {"role": "user",      "content": "블루카드로 독일 영주권 신청 기간이 얼마나 걸리나요?"},
            {"role": "assistant", "content": "앞서 안내드린 기준으로 블루카드 소지 후 33개월(독일어 B1) 또는 21개월(B1 충족)이면 영주권 신청 가능합니다."},
            {"role": "user",      "content": "그 중간에 실직하면 블루카드가 취소되나요?"}
        ],
        "expected_route": ["intent_classifier", "exception_handler"],
        "forbidden_route": [],
        "check_followup": False,        # 예외 상황 (신분 위기)
        "check_exception": "status_change",
        "check_country": "DE",
    },
    # T7: 동일 주제 구체 수치 질문 — is_followup=True
    {
        "id": "G3-08",
        "description": "T7 수치 확인 질문 — is_followup=True",
        "messages": _DE_BLUECARD_HISTORY + [
            {"role": "user", "content": "블루카드 최저 연봉 기준이 정확히 얼마인가요?"}
        ],
        "expected_route": ["intent_classifier", "response_formatter"],
        "forbidden_route": [],
        "check_followup": True,
        "check_exception": None,
        "check_country": "DE",
    },
    # T7: 부정 신호 + 국가 전환 없음 → 목적만 교체
    {
        "id": "G3-09",
        "description": "T7 부정 신호(목적 수정) — 국가 유지, 목적 교체",
        "messages": _DE_BLUECARD_HISTORY + [
            {"role": "user", "content": "아 미안해요, 사실은 취업이 아니라 독일 유학으로 가고 싶어요"}
        ],
        "expected_route": ["intent_classifier"],
        "forbidden_route": [],
        "check_followup": False,
        "check_exception": None,
        "check_country": "DE",
        "_extra_check": "purpose_study",   # purpose 가 'study'여야 함 (runner에서 별도 처리)
    },
    # T7: 완전 무관 질문 → general_chat 또는 response_formatter (비자 예외 경로 아님)
    {
        "id": "G3-10",
        "description": "T7 비자 무관 질문 → 예외/RAG 경로 없음 (general_chat or resp)",
        "messages": _DE_BLUECARD_HISTORY + [
            {"role": "user", "content": "독일 날씨는 어때요?"}
        ],
        "expected_route": ["intent_classifier"],
        "forbidden_route": ["exception_handler", "visa_rag_search"],
        "check_followup": False,
        "check_exception": None,
        "check_country": None,
    },
    # T8: 중복 질문 (T2에서 이미 물어본 것 재질문) → is_followup=True
    {
        "id": "G3-11",
        "description": "T8 이미 답한 내용 재질문 → is_followup=True(압축 재답)",
        "messages": _DE_BLUECARD_HISTORY + [
            {"role": "user",      "content": "블루카드로 독일 영주권 신청 기간이 얼마나 걸리나요?"},
            {"role": "assistant", "content": "앞서 안내드린 기준으로 33개월입니다."},
            {"role": "user",      "content": "다시 한번, 블루카드 처리 기간이 어떻게 되나요?"}
        ],
        "expected_route": ["intent_classifier", "response_formatter"],
        "forbidden_route": [],
        "check_followup": True,
        "check_exception": None,
        "check_country": "DE",
    },
    # T7: 긴급 처리 요청 → emergency exception
    {
        "id": "G3-12",
        "description": "T7 긴급 처리 요청 → exception_handler/emergency",
        "messages": _DE_BLUECARD_HISTORY + [
            {"role": "user", "content": "블루카드 긴급 발급이 가능한가요? 3주 안에 필요해요."}
        ],
        "expected_route": ["intent_classifier", "exception_handler"],
        "forbidden_route": [],
        "check_followup": False,
        "check_exception": "emergency",
        "check_country": "DE",
    },
    # T7: 구체적인 비자 번호/행정 절차 질문 → is_followup=True (RAG or WEB)
    {
        "id": "G3-13",
        "description": "T7 행정 절차 세부 질문 — is_followup=True",
        "messages": _DE_BLUECARD_HISTORY + [
            {"role": "user", "content": "블루카드 신청 서류를 독일 대사관에 직접 제출해야 하나요?"}
        ],
        "expected_route": ["intent_classifier", "response_formatter"],
        "forbidden_route": [],
        "check_followup": True,
        "check_exception": None,
        "check_country": "DE",
    },
]

# ──────────────────────────────────────────────────────────────────────
# Group 4 — 압축 워크플로우 엣지케이스: is_followup 오감지
# ──────────────────────────────────────────────────────────────────────
G4_FOLLOWUP_EDGE = [
    # FP: 첫 메시지에서 "서류는요?" → is_followup=False 여야 함
    {
        "id": "G4-01",
        "description": "첫 메시지가 후속처럼 보이는 표현 — is_followup=False",
        "messages": [
            {"role": "user", "content": "서류는요?"}
        ],
        "expected_route": ["intent_classifier"],
        "forbidden_route": [],
        "check_followup": False,
        "check_exception": None,
        "check_country": None,
    },
    # FP: 비자 명시 없이 "비용은요?" 첫 메시지
    {
        "id": "G4-02",
        "description": "첫 메시지 '비용은요?' — is_followup=False",
        "messages": [
            {"role": "user", "content": "비용은요?"}
        ],
        "expected_route": ["intent_classifier"],
        "forbidden_route": [],
        "check_followup": False,
        "check_exception": None,
        "check_country": None,
    },
    # 정상 후속 T2 — is_followup=True
    {
        "id": "G4-03",
        "description": "정상 T2 후속 — is_followup=True",
        "messages": [
            {"role": "user",      "content": "호주 워킹홀리데이 비자 조건이 어떻게 되나요?"},
            {"role": "assistant", "content": "호주 워킹홀리데이(462/417)는 만 18-30세(일부 31-35세)이고...\n## 추천 비자\n## 주요 자격 요건"},
            {"role": "user",      "content": "2차 비자로 연장할 때 농장 일 기간이 얼마나 필요한가요?"}
        ],
        "expected_route": ["intent_classifier", "response_formatter"],
        "forbidden_route": [],
        "check_followup": True,
        "check_exception": None,
        "check_country": "AU",
    },
    # FN: 주제 전환 후 — is_followup=False 여야 함
    {
        "id": "G4-04",
        "description": "주제 전환(국가 변경) — is_followup=False",
        "messages": [
            {"role": "user",      "content": "독일 블루카드 조건이 궁금해요"},
            {"role": "assistant", "content": "독일 블루카드는 학사 이상 학위와 연봉 기준이...\n## 추천 비자"},
            {"role": "user",      "content": "캐나다 취업비자는 어떻게 되나요?"}
        ],
        "expected_route": ["intent_classifier"],
        "forbidden_route": [],
        "check_followup": False,
        "check_exception": None,
        "check_country": "CA",
    },
    # 주제 전환 후 재후속 — is_followup=True (새 주제 기준)
    {
        "id": "G4-05",
        "description": "주제 전환 후 재후속 — 새 주제 기준 is_followup=True",
        "messages": [
            {"role": "user",      "content": "독일 블루카드 조건이 궁금해요"},
            {"role": "assistant", "content": "독일 블루카드는...\n## 추천 비자"},
            {"role": "user",      "content": "캐나다 취업비자는 어떻게 되나요?"},
            {"role": "assistant", "content": "캐나다 취업비자(LMIA 기반)는...\n## 추천 비자"},
            {"role": "user",      "content": "LMIA 비용은 어떻게 되나요?"}
        ],
        "expected_route": ["intent_classifier", "response_formatter"],
        "forbidden_route": [],
        "check_followup": True,
        "check_exception": None,
        "check_country": "CA",
    },
    # 오류 수정 후 후속 — "아니 유학" 같이 부정 후 is_followup=False
    {
        "id": "G4-06",
        "description": "부정 신호로 목적 수정 — is_followup=False (새 추천 시작)",
        "messages": [
            {"role": "user",      "content": "미국 취업비자 알려주세요"},
            {"role": "assistant", "content": "미국 취업비자(H-1B)는...\n## 추천 비자"},
            {"role": "user",      "content": "아니 사실은 유학 목적으로 가는 거예요"}
        ],
        "expected_route": ["intent_classifier"],
        "forbidden_route": [],
        "check_followup": False,
        "check_exception": None,
        "check_country": "US",
    },
    # 세부 질문이 연속 — T3, T4 모두 is_followup=True
    {
        "id": "G4-07",
        "description": "T3 연속 후속 — is_followup=True",
        "messages": [
            {"role": "user",      "content": "영국 학생비자 조건을 알고 싶어요"},
            {"role": "assistant", "content": "영국 학생비자(Student visa)는...\n## 추천 비자"},
            {"role": "user",      "content": "영어 점수 요건은 어떻게 되나요?"},
            {"role": "assistant", "content": "앞서 안내드린 영국 학생비자 기준으로, IELTS 6.0 이상이 필요합니다."},
            {"role": "user",      "content": "IELTS 대신 다른 시험도 인정되나요?"}
        ],
        "expected_route": ["intent_classifier", "response_formatter"],
        "forbidden_route": [],
        "check_followup": True,
        "check_exception": None,
        "check_country": "GB",
    },
    # 단 1개 prior 메시지 (역대 최소) → is_followup=True 가능
    {
        "id": "G4-08",
        "description": "이전 메시지 1개 후 후속 — is_followup=True",
        "messages": [
            {"role": "user",      "content": "일본 유학비자 종류가 궁금해요"},
            {"role": "assistant", "content": "일본 유학비자(留学)는...\n## 추천 비자"},
            {"role": "user",      "content": "기간이 얼마나 되나요?"}
        ],
        "expected_route": ["intent_classifier", "response_formatter"],
        "forbidden_route": [],
        "check_followup": True,
        "check_exception": None,
        "check_country": "JP",
    },
    # is_followup=True 이지만 내용이 비자 무관 → exception_handler 미진입
    {
        "id": "G4-09",
        "description": "비자 무관 잡담 — exception_handler/rag 미진입",
        "messages": [
            {"role": "user",      "content": "독일 블루카드 조건이 궁금해요"},
            {"role": "assistant", "content": "독일 블루카드는...\n## 추천 비자"},
            {"role": "user",      "content": "독일 음식은 어때요?"}
        ],
        "expected_route": ["intent_classifier"],
        "forbidden_route": ["exception_handler", "visa_rag_search"],
        "check_followup": False,
        "check_exception": None,
        "check_country": None,
    },
    # 압축 응답에 상위 참조 표현 포함 여부 — is_followup=True 일 때 응답 품질 체크
    {
        "id": "G4-10",
        "description": "is_followup=True 응답에 상위 참조 표현 포함 여부",
        "messages": [
            {"role": "user",      "content": "캐나다 Express Entry 점수 계산이 궁금해요"},
            {"role": "assistant", "content": "캐나다 Express Entry(EE)는 CRS 점수 기반 영주권 경로로...\n## 추천 비자"},
            {"role": "user",      "content": "CRS 점수를 높이는 방법은 무엇인가요?"}
        ],
        "expected_route": ["intent_classifier", "response_formatter"],
        "forbidden_route": [],
        "check_followup": True,
        "check_exception": None,
        "check_country": "CA",
        "_extra_check": "response_has_ref",   # 응답에 "앞서/이전/안내드린" 중 하나 포함
    },
]

# ──────────────────────────────────────────────────────────────────────
# 전체 시나리오 집합
# ──────────────────────────────────────────────────────────────────────
ALL_SCENARIOS = {
    "G1_STATUS_CHANGE": G1_STATUS_CHANGE,
    "G2_EXCEPTION_OTHER": G2_EXCEPTION_OTHER,
    "G3_DEEP_TURNS": G3_DEEP_TURNS,
    "G4_FOLLOWUP_EDGE": G4_FOLLOWUP_EDGE,
}

TOTAL = sum(len(v) for v in ALL_SCENARIOS.values())

if __name__ == "__main__":
    print(f"저신뢰 영역 검증 시나리오: 총 {TOTAL}개")
    for g, scenarios in ALL_SCENARIOS.items():
        print(f"  {g}: {len(scenarios)}개")
