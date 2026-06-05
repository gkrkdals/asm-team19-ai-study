"""
멀티턴 심화 검증 — 50개 시나리오
═══════════════════════════════════════════════════════════════════════
목적: 후속 대화 깊이 증가(5회+), 맥락 변경, 충돌/수정 상황에서의
      라우팅 정확도와 응답 품질 검증.

구성:
  Group A (15개) — 깊은 대화 (5~10회차 연속 턴)
  Group B (15개) — 맥락 전환 (국가/목적 변경, 국가 유지+목적 교체)
  Group C (10개) — 충돌 수정 (부정 패턴 "아니", "사실은", "X가 아니라 Y")
  Group D (10개) — 10회+ 연속 대화 (후속 질문 칩 기반 자동 연장)

데이터 구조: (phase, turns, expected_final_nodes, note)
  turns = [(user_msg, expected_nodes, description), ...]
  expected_nodes: 해당 턴에서 기대하는 노드 목록 (부분 일치 허용)

Group D의 경우 turns[0] 초기 질문 후 나머지는 후속 질문 칩에서 선택.
═══════════════════════════════════════════════════════════════════════
"""

# ─── Group A: 깊은 대화 (5~10회차) ──────────────────────────────────
# 국가·목적이 고정된 상태에서 점점 구체적인 질문으로 심화
GROUP_A = [
    # A1: 캐나다 취업 — 5턴 심화
    ("A1_deep_5turn", [
        ("캐나다에서 소프트웨어 개발자로 취업하고 싶어요",
         ["intent_classifier", "visa_rag_search"], "초기 요청"),
        ("Express Entry 점수가 어느 정도면 돼요?",
         ["intent_classifier", "visa_rag_search"], "구체 조건 심화"),
        ("IELTS 점수는 몇 점이 필요한가요?",
         ["intent_classifier", "visa_rag_search"], "언어 요건 심화"),
        ("캐나다 이민 신청 비용은 얼마예요?",
         ["intent_classifier", "visa_rag_search"], "비용 심화"),
        ("처리 기간은 보통 얼마나 걸려요?",
         ["intent_classifier", "visa_rag_search"], "기간 심화"),
    ], "캐나다 취업 5턴 심화 — 국가·목적 일관성 검증"),

    # A2: 일본 유학 — 6턴
    ("A2_deep_6turn", [
        ("일본에서 대학원 유학을 하고 싶어요",
         ["intent_classifier", "visa_rag_search"], "초기"),
        ("일본 학생비자 신청 절차를 알려주세요",
         ["intent_classifier", "visa_rag_search"], "절차"),
        ("재정보증서는 어떻게 준비하나요?",
         ["intent_classifier", "visa_rag_search"], "서류"),
        ("유학 중에 아르바이트가 가능한가요?",
         ["intent_classifier", "visa_rag_search"], "추가 조건"),
        ("비자 갱신은 어떻게 하나요?",
         ["intent_classifier", "visa_rag_search"], "갱신"),
        ("졸업 후 취업비자로 전환할 수 있나요?",
         ["intent_classifier", "exception_handler"], "신분변경"),
    ], "일본 유학 6턴 — 신분 변경까지"),

    # A3: 독일 취업 — 5턴
    ("A3_deep_5turn_de", [
        ("독일에서 엔지니어로 취업하고 싶어요",
         ["intent_classifier", "visa_rag_search"], "초기"),
        ("독일 블루카드 요건이 뭐예요?",
         ["intent_classifier", "visa_rag_search"], "블루카드"),
        ("급여 기준은 얼마인가요?",
         ["intent_classifier", "visa_rag_search"], "급여"),
        ("독일어를 못해도 신청이 가능한가요?",
         ["intent_classifier", "visa_rag_search"], "언어"),
        ("가족도 함께 올 수 있나요?",
         ["intent_classifier", "visa_rag_search"], "동반가족"),
    ], "독일 취업 5턴"),

    # A4: 호주 워킹홀리데이 — 5턴
    ("A4_deep_5turn_au", [
        ("호주 워킹홀리데이 비자 받고 싶어요",
         ["intent_classifier", "visa_rag_search"], "초기"),
        ("나이 제한이 있나요?",
         ["intent_classifier", "visa_rag_search"], "나이"),
        ("신청 비용은 얼마예요?",
         ["intent_classifier", "visa_rag_search"], "비용"),
        ("2년차 비자는 어떻게 받나요?",
         ["intent_classifier", "visa_rag_search"], "연장"),
        ("호주에서 일할 수 있는 업종이 제한되나요?",
         ["intent_classifier", "visa_rag_search"], "업종"),
    ], "호주 워킹홀리데이 5턴"),

    # A5: 미국 취업 — 7턴
    ("A5_deep_7turn_us", [
        ("미국에서 IT 개발자로 취업하고 싶어요",
         ["intent_classifier", "visa_rag_search"], "초기"),
        ("H-1B 비자 추첨 방식을 설명해주세요",
         ["intent_classifier", "visa_rag_search"], "H-1B"),
        ("스폰서 회사를 어떻게 찾나요?",
         ["intent_classifier", "visa_rag_search"], "스폰서"),
        ("OPT로 먼저 일하는 방법이 있나요?",
         ["intent_classifier", "visa_rag_search"], "OPT"),
        ("H-1B 탈락 시 대안이 있나요?",
         ["intent_classifier", "visa_rag_search"], "대안"),
        ("영주권(그린카드)으로 전환은 언제 가능한가요?",
         ["intent_classifier", "exception_handler"], "영주권"),
        ("가족 비자(H-4)도 함께 신청 가능한가요?",
         ["intent_classifier", "visa_rag_search"], "가족"),
    ], "미국 취업 7턴 — 복잡 경로"),

    # A6~A15: 추가 깊은 대화 시나리오
    ("A6_deep_5turn_gb", [
        ("영국에서 간호사로 취업하고 싶어요", ["intent_classifier", "visa_rag_search"], "초기"),
        ("Skilled Worker Visa 요건이 뭔가요?", ["intent_classifier", "visa_rag_search"], "조건"),
        ("NMC 등록은 어떻게 하나요?", ["intent_classifier", "visa_rag_search"], "자격"),
        ("영어 시험은 어떤 걸 봐야 하나요?", ["intent_classifier", "visa_rag_search"], "언어"),
        ("비자 처리 기간은요?", ["intent_classifier", "visa_rag_search"], "기간"),
    ], "영국 간호사 취업 5턴"),

    ("A7_deep_5turn_ca_study", [
        ("캐나다 대학교 유학 정보 알려주세요", ["intent_classifier", "visa_rag_search"], "초기"),
        ("학생비자 신청 시 필요한 서류는?", ["intent_classifier", "visa_rag_search"], "서류"),
        ("재정 증명은 얼마나 필요한가요?", ["intent_classifier", "visa_rag_search"], "재정"),
        ("캐나다에서 파트타임 일을 할 수 있나요?", ["intent_classifier", "visa_rag_search"], "아르바이트"),
        ("졸업 후 취업 비자(PGWP) 알려주세요", ["intent_classifier", "visa_rag_search"], "PGWP"),
    ], "캐나다 유학 5턴"),

    ("A8_deep_6turn_au_employment", [
        ("호주에서 요리사로 취업하고 싶어요", ["intent_classifier", "visa_rag_search"], "초기"),
        ("Skilled Nominated Visa(190) 설명해줘", ["intent_classifier", "visa_rag_search"], "비자종류"),
        ("직업 스킬 평가는 어디서 받나요?", ["intent_classifier", "visa_rag_search"], "평가"),
        ("주정부 지명을 받으려면?", ["intent_classifier", "visa_rag_search"], "주정부"),
        ("영어 점수는 얼마나 필요해요?", ["intent_classifier", "visa_rag_search"], "영어"),
        ("신청비는 얼마인가요?", ["intent_classifier", "visa_rag_search"], "비용"),
    ], "호주 요리사 취업 6턴"),

    ("A9_deep_5turn_jp_employment", [
        ("일본에서 IT 회사에 취업하고 싶어요", ["intent_classifier", "visa_rag_search"], "초기"),
        ("기술·인문지식·국제업무 비자가 맞나요?", ["intent_classifier", "visa_rag_search"], "비자확인"),
        ("일본어 능력이 없어도 되나요?", ["intent_classifier", "visa_rag_search"], "언어"),
        ("비자 신청은 회사에서 해주나요?", ["intent_classifier", "visa_rag_search"], "절차"),
        ("체류기간은 얼마나 되나요?", ["intent_classifier", "visa_rag_search"], "기간"),
    ], "일본 IT 취업 5턴"),

    ("A10_deep_5turn_de_study", [
        ("독일 대학에서 공부하고 싶어요", ["intent_classifier", "visa_rag_search"], "초기"),
        ("독일 학생비자 신청 방법은?", ["intent_classifier", "visa_rag_search"], "절차"),
        ("재정 증명 방법을 알려주세요", ["intent_classifier", "visa_rag_search"], "재정"),
        ("독일어 없이도 영어로 수업 들을 수 있나요?", ["intent_classifier", "visa_rag_search"], "언어"),
        ("졸업 후 독일에서 일할 수 있나요?", ["intent_classifier", "visa_rag_search"], "취업전환"),
    ], "독일 유학 5턴"),

    ("A11_deep_5turn_us_study", [
        ("미국 대학원 유학하고 싶어요", ["intent_classifier", "visa_rag_search"], "초기"),
        ("F-1 비자 신청 절차 알려주세요", ["intent_classifier", "visa_rag_search"], "F-1"),
        ("SEVIS 비용은 얼마예요?", ["intent_classifier", "visa_rag_search"], "SEVIS"),
        ("비자 인터뷰에서 자주 물어보는 것은?", ["intent_classifier", "visa_rag_search"], "인터뷰"),
        ("OPT 신청 시기는 언제인가요?", ["intent_classifier", "visa_rag_search"], "OPT"),
    ], "미국 유학 5턴"),

    ("A12_deep_5turn_gb_study", [
        ("영국 대학교에서 유학하고 싶어요", ["intent_classifier", "visa_rag_search"], "초기"),
        ("Student Visa 신청 조건은?", ["intent_classifier", "visa_rag_search"], "조건"),
        ("영어 점수 기준을 알려주세요", ["intent_classifier", "visa_rag_search"], "영어"),
        ("CAS 번호는 무엇인가요?", ["intent_classifier", "visa_rag_search"], "CAS"),
        ("학업 중 일을 할 수 있나요?", ["intent_classifier", "visa_rag_search"], "아르바이트"),
    ], "영국 유학 5턴"),

    ("A13_deep_5turn_ca_long", [
        ("캐나다에서 장기 거주하고 싶어요", ["intent_classifier", "visa_rag_search"], "초기"),
        ("PR(영주권) 취득 방법은?", ["intent_classifier", "visa_rag_search"], "PR"),
        ("Express Entry 점수 계산 방법은?", ["intent_classifier", "visa_rag_search"], "점수"),
        ("주정부 이민 프로그램(PNP)도 있나요?", ["intent_classifier", "visa_rag_search"], "PNP"),
        ("PR 취득 후 시민권 신청은 얼마나 걸려요?", ["intent_classifier", "visa_rag_search"], "시민권"),
    ], "캐나다 장기거주 5턴"),

    ("A14_deep_6turn_au_long", [
        ("호주에서 영주권을 받고 싶어요", ["intent_classifier", "visa_rag_search"], "초기"),
        ("Skilled Independent Visa(189) 알려주세요", ["intent_classifier", "visa_rag_search"], "189비자"),
        ("직업군 목록 확인은 어떻게 하나요?", ["intent_classifier", "visa_rag_search"], "직업군"),
        ("포인트 계산 기준은?", ["intent_classifier", "visa_rag_search"], "포인트"),
        ("신청 후 얼마나 기다려야 하나요?", ["intent_classifier", "visa_rag_search"], "대기"),
        ("영주권 후 시민권 신청은요?", ["intent_classifier", "visa_rag_search"], "시민권"),
    ], "호주 영주권 6턴"),

    ("A15_deep_5turn_gb_long", [
        ("영국에서 장기 거주하고 싶어요", ["intent_classifier", "visa_rag_search"], "초기"),
        ("Indefinite Leave to Remain(ILR) 조건은?", ["intent_classifier", "visa_rag_search"], "ILR"),
        ("5년 거주 요건 계산은 어떻게 하나요?", ["intent_classifier", "visa_rag_search"], "거주요건"),
        ("Life in the UK 시험은 뭔가요?", ["intent_classifier", "visa_rag_search"], "시험"),
        ("ILR 후 시민권(British)으로 전환은?", ["intent_classifier", "visa_rag_search"], "시민권"),
    ], "영국 장기거주 5턴"),
]

# ─── Group B: 맥락 전환 ──────────────────────────────────────────────
GROUP_B = [
    # B1: 국가 전환 (캐나다→호주), 목적 유지
    ("B1_country_switch", [
        ("캐나다에서 취업하고 싶어요", ["intent_classifier", "visa_rag_search"], "캐나다"),
        ("그럼 호주는 어때요?", ["intent_classifier", "visa_rag_search"], "호주로 전환"),
        ("호주 취업비자 신청 절차도 알려주세요", ["intent_classifier", "visa_rag_search"], "호주 상세"),
    ], "국가 전환 캐나다→호주, 취업 목적 유지"),

    # B2: 목적 전환 (유학→취업), 국가 유지
    ("B2_purpose_switch", [
        ("일본 유학 비자 알려주세요", ["intent_classifier", "visa_rag_search"], "유학"),
        ("졸업 후 일본에서 취업하려면요?", ["intent_classifier", "visa_rag_search"], "취업으로 전환"),
        ("취업비자 조건을 자세히 알려주세요", ["intent_classifier", "visa_rag_search"], "취업 상세"),
    ], "목적 전환 유학→취업, 일본 유지"),

    # B3: 국가+목적 동시 전환
    ("B3_full_switch", [
        ("미국 여행 비자 알려주세요", ["intent_classifier", "visa_rag_search"], "미국 여행"),
        ("독일에서 취업하고 싶어요", ["intent_classifier", "visa_rag_search"], "독일 취업"),
    ], "국가+목적 동시 전환"),

    # B4: 3개국 순환
    ("B4_triple_switch", [
        ("캐나다 취업비자 알려주세요", ["intent_classifier", "visa_rag_search"], "캐나다"),
        ("영국은 어때요?", ["intent_classifier", "visa_rag_search"], "영국"),
        ("호주는요?", ["intent_classifier", "visa_rag_search"], "호주"),
    ], "3개국 순환 전환"),

    # B5: 같은 나라, 목적 세분화
    ("B5_purpose_detail", [
        ("독일 비자 알려주세요", ["intent_classifier"], "일반"),
        ("취업 비자로요", ["intent_classifier", "visa_rag_search"], "목적 명확화"),
        ("특히 IT 개발자 비자는요?", ["intent_classifier", "visa_rag_search"], "직업 심화"),
    ], "목적 점진적 구체화"),

    # B6: 장기거주로 전환
    ("B6_to_long_stay", [
        ("캐나다 여행 비자 정보 주세요", ["intent_classifier", "visa_rag_search"], "여행"),
        ("그냥 캐나다에 오래 살고 싶어요", ["intent_classifier", "visa_rag_search"], "장기거주 전환"),
    ], "여행→장기거주 전환"),

    # B7: 워킹홀리데이 → 취업 전환
    ("B7_wh_to_work", [
        ("호주 워킹홀리데이 하고 싶어요", ["intent_classifier", "visa_rag_search"], "워홀"),
        ("그 후에 정식 취업비자로 전환하려면요?", ["intent_classifier", "visa_rag_search"], "취업 전환"),
    ], "워홀→취업 전환"),

    # B8: 국가 전환 후 상세 질문
    ("B8_switch_detail", [
        ("영국 취업비자 알려주세요", ["intent_classifier", "visa_rag_search"], "영국"),
        ("미국도 알려줘요", ["intent_classifier", "visa_rag_search"], "미국"),
        ("어느 나라가 더 빨리 받을 수 있나요?", ["intent_classifier", "visa_rag_search"], "비교"),
    ], "국가 전환 후 비교 질문"),

    # B9: 가족 동반으로 목적 확장
    ("B9_family_extend", [
        ("미국 취업비자 정보 주세요", ["intent_classifier", "visa_rag_search"], "개인"),
        ("배우자도 같이 갈 수 있나요?", ["intent_classifier", "visa_rag_search"], "가족 추가"),
        ("아이 비자도 같이 신청 가능한가요?", ["intent_classifier", "visa_rag_search"], "자녀"),
    ], "가족 동반 목적 확장"),

    # B10: 단기→장기 체류 전환
    ("B10_short_to_long", [
        ("일본 단기 여행 비자 알려줘요", ["intent_classifier", "visa_rag_search"], "단기"),
        ("3개월 더 머물고 싶어요", ["intent_classifier", "exception_handler"], "체류연장"),
    ], "단기→체류연장 전환"),

    # B11: 여행 → 유학
    ("B11_travel_to_study", [
        ("영국 여행 가려고 해요", ["intent_classifier", "visa_rag_search"], "여행"),
        ("영국에서 영어 어학연수 하고 싶어요", ["intent_classifier", "visa_rag_search"], "유학 전환"),
    ], "여행→유학 전환"),

    # B12: 국가 전환 + 직업 유지
    ("B12_country_change_job_keep", [
        ("독일에서 의사로 일하고 싶어요", ["intent_classifier", "visa_rag_search"], "독일 의사"),
        ("그럼 영국에서는요?", ["intent_classifier", "visa_rag_search"], "영국 의사"),
    ], "직업 유지 + 국가 전환"),

    # B13: 비자 종류 변경 요청
    ("B13_visa_type_change", [
        ("캐나다 관광비자로 입국하려고요", ["intent_classifier", "visa_rag_search"], "관광"),
        ("입국 후 취업 가능한가요?", ["intent_classifier", "exception_handler"], "신분변경"),
    ], "관광→취업 신분변경"),

    # B14: 복수 국가 비교
    ("B14_compare", [
        ("캐나다 유학 비자 알려주세요", ["intent_classifier", "visa_rag_search"], "캐나다"),
        ("호주 유학 비자는요?", ["intent_classifier", "visa_rag_search"], "호주"),
        ("어느 나라가 학생 비자 받기 쉬운가요?", ["intent_classifier", "visa_rag_search"], "비교"),
    ], "유학 국가 비교"),

    # B15: 장기 체류 → 영주권 전환
    ("B15_long_to_pr", [
        ("호주에서 2년 살고 싶어요", ["intent_classifier", "visa_rag_search"], "장기거주"),
        ("그 후 영주권을 받을 수 있나요?", ["intent_classifier", "visa_rag_search"], "영주권"),
    ], "장기거주→영주권 전환"),
]

# ─── Group C: 충돌/수정 패턴 ────────────────────────────────────────
GROUP_C = [
    # C1: "아니" 부정 + 국가 보존
    ("C1_negation_keep_country", [
        ("일본에서 관광비자로 가려고요", ["intent_classifier", "visa_rag_search"], "관광"),
        ("아니, 사실은 일본에서 취업하고 싶어요", ["intent_classifier", "visa_rag_search"], "수정 — 국가 유지"),
    ], "부정 신호 후 국가 보존, 목적 교체"),

    # C2: "X가 아니라 Y" 충돌
    ("C2_conflict_pattern", [
        ("캐나다에서 관광이 아니라 취업으로 가고 싶어요", ["intent_classifier", "visa_rag_search"], "충돌 패턴"),
    ], "X가 아니라 Y 충돌 패턴"),

    # C3: "사실은" 수정
    ("C3_sashiwa_correction", [
        ("독일에서 유학하려고 해요", ["intent_classifier", "visa_rag_search"], "유학"),
        ("사실은 독일에서 일하고 싶어요", ["intent_classifier", "visa_rag_search"], "수정"),
    ], "사실은 수정 패턴 — 국가 유지"),

    # C4: 직업 수정
    ("C4_profession_correction", [
        ("캐나다에서 요리사로 취업하고 싶어요", ["intent_classifier", "visa_rag_search"], "요리사"),
        ("아니 요리사 말고 IT 개발자로요", ["intent_classifier", "visa_rag_search"], "직업 수정"),
    ], "직업 수정 — 국가·목적 유지"),

    # C5: 다시 생각해보니 패턴
    ("C5_reconsider", [
        ("영국에서 워킹홀리데이 하고 싶어요", ["intent_classifier", "visa_rag_search"], "워홀"),
        ("다시 생각해보니 영국에서 유학이 더 나을 것 같아요", ["intent_classifier", "visa_rag_search"], "재고"),
    ], "재고 패턴 — 국가 유지"),

    # C6: 여행→취업 충돌
    ("C6_travel_not_work", [
        ("미국에서 여행이 아니라 취업 비자가 필요해요", ["intent_classifier", "visa_rag_search"], "충돌"),
    ], "여행이 아니라 취업 — 취업 추출"),

    # C7: 장기 대화 중 수정
    ("C7_correction_in_deep", [
        ("호주에서 유학하고 싶어요", ["intent_classifier", "visa_rag_search"], "유학"),
        ("비자 신청 비용이 얼마예요?", ["intent_classifier", "visa_rag_search"], "비용"),
        ("아, 죄송한데 사실 취업 비자를 원해요", ["intent_classifier", "visa_rag_search"], "수정"),
        ("호주 취업 비자 조건을 알려주세요", ["intent_classifier", "visa_rag_search"], "수정 후 계속"),
    ], "3턴 후 수정 패턴"),

    # C8: 국가 수정
    ("C8_country_correction", [
        ("일본 유학 비자 알려주세요", ["intent_classifier", "visa_rag_search"], "일본"),
        ("아, 저 일본이 아니라 한국에서 공부하려던 거예요... 아니 호주요", ["intent_classifier", "visa_rag_search"], "국가 수정"),
    ], "국가 수정 패턴"),

    # C9: 이민이 아니라 단기 체류
    ("C9_immigration_not", [
        ("독일에서 이민이 아니라 단기 체류를 원해요", ["intent_classifier", "visa_rag_search"], "단기체류"),
    ], "이민이 아니라 단기 패턴"),

    # C10: 복합 수정 (국가+목적)
    ("C10_full_correction", [
        ("미국에서 취업하고 싶어요", ["intent_classifier", "visa_rag_search"], "미국 취업"),
        ("아니 사실 캐나다에서 유학하려고요", ["intent_classifier", "visa_rag_search"], "전체 수정"),
    ], "국가+목적 동시 수정"),
]

# ─── Group D: 10회+ 연속 대화 (후속 질문 기반 자동 연장) ──────────────
# 첫 질문 후 AI 후속 질문 칩에서 선택해서 이어가는 시나리오
# runner에서 /chat/followups 결과를 다음 turn 입력으로 사용
GROUP_D = [
    # D1: 캐나다 취업 10턴 (후속 질문 자동 연장)
    ("D1_auto_extend_ca", [
        ("캐나다에서 데이터 사이언티스트로 취업하고 싶어요",
         ["intent_classifier", "visa_rag_search"], "seed"),
        # 이후 9개 턴은 runner가 followup 칩에서 자동 선택
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 1"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 2"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 3"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 4"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 5"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 6"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 7"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 8"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 9"),
    ], "캐나다 취업 10턴 — 후속질문 자동연장"),

    # D2: 호주 유학 10턴
    ("D2_auto_extend_au_study", [
        ("호주 대학교 입학해서 유학하고 싶어요",
         ["intent_classifier", "visa_rag_search"], "seed"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 1"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 2"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 3"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 4"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 5"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 6"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 7"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 8"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 9"),
    ], "호주 유학 10턴 — 후속질문 자동연장"),

    # D3: 미국 취업 10턴
    ("D3_auto_extend_us", [
        ("미국에서 금융 분야 취업을 원해요",
         ["intent_classifier", "visa_rag_search"], "seed"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 1"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 2"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 3"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 4"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 5"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 6"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 7"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 8"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 9"),
    ], "미국 금융 취업 10턴"),

    # D4: 독일 이민 12턴
    ("D4_auto_extend_de_12", [
        ("독일에서 엔지니어로 일하다가 영주권까지 받고 싶어요",
         ["intent_classifier", "visa_rag_search"], "seed"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 1"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 2"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 3"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 4"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 5"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 6"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 7"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 8"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 9"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 10"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 11"),
    ], "독일 엔지니어→영주권 12턴"),

    # D5: 영국 유학→취업 10턴
    ("D5_auto_extend_gb_10", [
        ("영국에서 MBA를 마치고 취업까지 하고 싶어요",
         ["intent_classifier", "visa_rag_search"], "seed"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 1"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 2"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 3"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 4"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 5"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 6"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 7"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 8"),
        ("__followup__", ["intent_classifier", "visa_rag_search"], "followup 9"),
    ], "영국 MBA→취업 10턴"),

    # D6~D10: 추가 자동 연장 시나리오 (10턴)
    ("D6_auto_extend_jp_10", [
        ("일본에서 애니메이션 회사에 취업하고 싶어요", ["intent_classifier", "visa_rag_search"], "seed"),
        *[("__followup__", ["intent_classifier", "visa_rag_search"], f"followup {i}") for i in range(1, 10)],
    ], "일본 애니메이션 취업 10턴"),

    ("D7_auto_extend_ca_pr_10", [
        ("캐나다 영주권 취득 방법을 처음부터 알려주세요", ["intent_classifier", "visa_rag_search"], "seed"),
        *[("__followup__", ["intent_classifier", "visa_rag_search"], f"followup {i}") for i in range(1, 10)],
    ], "캐나다 영주권 10턴"),

    ("D8_auto_extend_au_work_10", [
        ("호주에서 간호사로 취업해서 영주권까지 받고 싶어요", ["intent_classifier", "visa_rag_search"], "seed"),
        *[("__followup__", ["intent_classifier", "visa_rag_search"], f"followup {i}") for i in range(1, 10)],
    ], "호주 간호사→영주권 10턴"),

    ("D9_auto_extend_gb_work_10", [
        ("영국에서 IT 컨설턴트로 일하다 장기 거주하고 싶어요", ["intent_classifier", "visa_rag_search"], "seed"),
        *[("__followup__", ["intent_classifier", "visa_rag_search"], f"followup {i}") for i in range(1, 10)],
    ], "영국 IT→장기거주 10턴"),

    ("D10_auto_extend_de_study_10", [
        ("독일 뮌헨공대(TUM)에서 석사 유학 후 취업까지 하고 싶어요", ["intent_classifier", "visa_rag_search"], "seed"),
        *[("__followup__", ["intent_classifier", "visa_rag_search"], f"followup {i}") for i in range(1, 10)],
    ], "독일 TUM 유학→취업 10턴"),
]

ALL_SCENARIOS = [
    *[(s[0], "A_deep",   s[1], s[2]) for s in GROUP_A],
    *[(s[0], "B_switch", s[1], s[2]) for s in GROUP_B],
    *[(s[0], "C_conflict",s[1], s[2]) for s in GROUP_C],
    *[(s[0], "D_auto",   s[1], s[2]) for s in GROUP_D],
]

if __name__ == "__main__":
    total = sum(len(s[2]) for s in ALL_SCENARIOS)
    print(f"총 시나리오: {len(ALL_SCENARIOS)}개, 총 턴: {total}개")
    for sid, phase, turns, note in ALL_SCENARIOS:
        auto = sum(1 for t in turns if t[0] == "__followup__")
        print(f"  [{phase}] {sid}: {len(turns)}턴 (자동{auto}) — {note}")
