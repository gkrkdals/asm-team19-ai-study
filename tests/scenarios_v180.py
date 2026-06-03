"""
VisaGuideAI 종합 검증 데이터셋 — v180
════════════════════════════════════════════════════════════════
구성: 기본 150개 (10 카테고리 × 15개) + 특수 30개 (멀티턴·상충·모호·긴급)
설계: claude-sonnet-4-6 (데이터 품질 검토 완료)
실행: claude-haiku-4-5 (API 배치 호출)
형식: (msg, category, expected_nodes, history)
  - history: None 또는 [{"role": "user"|"assistant", "content": "..."}]
  - expected_nodes: 라우팅 결과에 포함돼야 할 노드 이름 리스트(하나라도 포함되면 PASS)
════════════════════════════════════════════════════════════════
"""

# ── 카테고리 상수 ─────────────────────────────────────────────────────────────
CAT_EMPLOYMENT   = "employment"
CAT_STUDY        = "study"
CAT_EXTENSION    = "extension"
CAT_STATUS       = "status_change"
CAT_CROSS        = "cross_rule"
CAT_LONG         = "long_stay"
CAT_DEEP         = "deep_search"
CAT_REACTION     = "reaction"
CAT_OFFTOPIC     = "off_topic"
CAT_NEWCOUNTRY   = "new_country"
CAT_MULTITURN    = "multi_turn"
CAT_CONFLICT     = "conflicting"
CAT_VAGUE        = "vague"
CAT_EDGE         = "edge_case"

# ══════════════════════════════════════════════════════════════════════════════
# 기본 150개
# ══════════════════════════════════════════════════════════════════════════════

BASIC_EMPLOYMENT = [
    # 15개 / 기대 노드: visa_rag_search
    ("캐나다에서 개발자로 취업하고 싶어요",                      CAT_EMPLOYMENT, ["visa_rag_search"], None),
    ("미국 H1B 비자 신청 조건이 궁금해요",                      CAT_EMPLOYMENT, ["visa_rag_search"], None),
    ("호주에서 IT 엔지니어로 일하고 싶습니다",                   CAT_EMPLOYMENT, ["visa_rag_search"], None),
    ("독일에서 취업비자를 받는 방법은?",                         CAT_EMPLOYMENT, ["visa_rag_search"], None),
    ("일본에서 워킹홀리데이로 일할 수 있나요?",                  CAT_EMPLOYMENT, ["visa_rag_search"], None),
    ("영국 Tier 2 취업비자 조건이 뭔가요?",                     CAT_EMPLOYMENT, ["visa_rag_search"], None),
    ("프랑스에서 취업하려면 어떤 비자가 필요한가요?",             CAT_EMPLOYMENT, ["visa_rag_search"], None),
    ("싱가포르 취업 비자 종류와 조건은 어떻게 되나요?",          CAT_EMPLOYMENT, ["visa_rag_search"], None),
    ("캐나다 익스프레스 엔트리로 취업비자를 받을 수 있나요?",     CAT_EMPLOYMENT, ["visa_rag_search"], None),
    ("미국 L1 비자로 내부 이직이 가능한가요?",                  CAT_EMPLOYMENT, ["visa_rag_search"], None),
    ("인도에서 기술자로 취업할 수 있는 비자 종류는?",            CAT_EMPLOYMENT, ["visa_rag_search"], None),
    ("태국에서 일하고 싶은데 취업비자가 있나요?",                CAT_EMPLOYMENT, ["visa_rag_search"], None),
    ("남아공에서 취업하고 싶어요, 비자가 필요한가요?",           CAT_EMPLOYMENT, ["visa_rag_search"], None),
    ("뉴질랜드 취업비자 신청 조건은 무엇인가요?",                CAT_EMPLOYMENT, ["visa_rag_search"], None),
    ("브라질에서 취업 가능한 비자 종류를 알려주세요",             CAT_EMPLOYMENT, ["visa_rag_search"], None),
]

BASIC_STUDY = [
    # 15개 / 기대 노드: visa_rag_search
    ("미국 대학원에 진학하려면 F1 비자가 필요한가요?",           CAT_STUDY, ["visa_rag_search"], None),
    ("영국 유학생 비자 신청 요건을 알려주세요",                  CAT_STUDY, ["visa_rag_search"], None),
    ("캐나다 유학 비자 최대 체류 기간은 얼마인가요?",            CAT_STUDY, ["visa_rag_search"], None),
    ("호주 학생비자로 아르바이트가 가능한가요?",                  CAT_STUDY, ["visa_rag_search"], None),
    ("일본 어학연수 비자 신청 방법을 알려주세요",                CAT_STUDY, ["visa_rag_search"], None),
    ("독일 대학원 입학 후 비자 비용은 얼마인가요?",              CAT_STUDY, ["visa_rag_search"], None),
    ("뉴질랜드 유학비자 신청 절차를 알려주세요",                 CAT_STUDY, ["visa_rag_search"], None),
    ("싱가포르 대학원 유학비자 조건은 어떻게 되나요?",           CAT_STUDY, ["visa_rag_search"], None),
    ("프랑스 유학비자로 파트타임 근무가 가능한가요?",             CAT_STUDY, ["visa_rag_search"], None),
    ("캐나다에서 유학 후 취업비자로 전환하는 방법은?",           CAT_STUDY, ["visa_rag_search"], None),
    ("남아공 대학 유학비자는 어떻게 신청하나요?",                CAT_STUDY, ["visa_rag_search"], None),
    ("태국 어학원 등록 후 학생비자를 받는 방법은?",              CAT_STUDY, ["visa_rag_search"], None),
    ("인도 대학원 유학비자 필요 요건은 무엇인가요?",             CAT_STUDY, ["visa_rag_search"], None),
    ("말레이시아 유학비자 신청 조건이 뭔가요?",                  CAT_STUDY, ["visa_rag_search"], None),
    ("필리핀 어학연수 비자 종류와 체류 기간은?",                 CAT_STUDY, ["visa_rag_search"], None),
]

BASIC_EXTENSION = [
    # 15개 / 기대 노드: exception_handler
    ("미국 관광비자 체류 기간 연장이 가능한가요?",               CAT_EXTENSION, ["exception_handler"], None),
    ("한국에서 장기 체류를 연장하고 싶어요",                     CAT_EXTENSION, ["exception_handler"], None),
    ("캐나다 학생비자 유효기간 연장은 어떻게 하나요?",           CAT_EXTENSION, ["exception_handler"], None),
    ("일본 관광비자 체류기간을 연장할 수 있나요?",               CAT_EXTENSION, ["exception_handler"], None),
    ("호주 워킹홀리데이 비자 2년차 신청이 가능한가요?",          CAT_EXTENSION, ["exception_handler"], None),
    ("미국 비자 I-539 폼으로 체류 연장하는 방법은?",            CAT_EXTENSION, ["exception_handler"], None),
    ("영국 비자 만료 전 연장 신청 가능한 기간은 언제인가요?",    CAT_EXTENSION, ["exception_handler"], None),
    ("독일 비자 유효기간 연장이 가능한가요?",                    CAT_EXTENSION, ["exception_handler"], None),
    ("프랑스에서 거주 기간을 연장하고 싶어요",                   CAT_EXTENSION, ["exception_handler"], None),
    ("싱가포르 체류 기간 연장 방법을 알려주세요",                CAT_EXTENSION, ["exception_handler"], None),
    ("뉴질랜드 비자 갱신 절차를 알려주세요",                     CAT_EXTENSION, ["exception_handler"], None),
    ("캐나다에서 관광비자로 왔다가 학생비자로 변경 전 연장이 필요한가요?", CAT_EXTENSION, ["exception_handler"], None),
    ("미국에 3개월을 추가로 더 머물 수 있는 방법이 있나요?",     CAT_EXTENSION, ["exception_handler"], None),
    ("호주 학생비자가 만료되기 전에 연장 신청을 해야 하나요?",   CAT_EXTENSION, ["exception_handler"], None),
    ("일본 장기체류 비자 갱신 절차는 어떻게 되나요?",            CAT_EXTENSION, ["exception_handler"], None),
]

BASIC_STATUS_CHANGE = [
    # 15개 / 기대 노드: exception_handler
    ("일본에서 관광비자로 입국 후 취업비자로 변경이 가능한가요?",  CAT_STATUS, ["exception_handler"], None),
    ("호주에서 학생비자를 워킹홀리데이 비자로 전환할 수 있나요?",  CAT_STATUS, ["exception_handler"], None),
    ("미국 관광비자를 취업비자로 전환하는 방법은?",               CAT_STATUS, ["exception_handler"], None),
    ("캐나다에서 관광비자를 유학비자로 변경하려면?",               CAT_STATUS, ["exception_handler"], None),
    ("일반 취업비자에서 영주권으로 신분을 변경하는 절차는?",       CAT_STATUS, ["exception_handler"], None),
    ("영국 학생비자 만료 후 취업비자로 신청할 수 있나요?",         CAT_STATUS, ["exception_handler"], None),
    ("프랑스에서 관광 후 취업비자로 전환 가능한가요?",             CAT_STATUS, ["exception_handler"], None),
    ("독일 비자 유형을 변경하는 절차가 어떻게 되나요?",            CAT_STATUS, ["exception_handler"], None),
    ("호주 워킹홀리데이 비자 후 영주권 신청이 가능한가요?",        CAT_STATUS, ["exception_handler"], None),
    ("캐나다에서 유학비자를 이민비자로 전환하려면 어떻게 하나요?", CAT_STATUS, ["exception_handler"], None),
    ("미국에서 비자 종류를 업그레이드할 수 있는 방법이 있나요?",   CAT_STATUS, ["exception_handler"], None),
    ("싱가포르 비자가 일시 정지된 경우 재개 절차는?",             CAT_STATUS, ["exception_handler"], None),
    ("태국에서 관광비자를 장기거주비자로 변경하려면?",             CAT_STATUS, ["exception_handler"], None),
    ("인도에서 학생비자를 취업비자로 직접 전환할 수 있나요?",      CAT_STATUS, ["exception_handler"], None),
    ("브라질 비자 종류를 변경하는 것이 가능한가요?",               CAT_STATUS, ["exception_handler"], None),
]

BASIC_CROSS_RULE = [
    # 15개 / 기대 노드: exception_handler
    ("쉥겐 비자로 영국에도 입국할 수 있나요?",                   CAT_CROSS, ["exception_handler"], None),
    ("미국을 경유할 때 환승비자가 별도로 필요한가요?",            CAT_CROSS, ["exception_handler"], None),
    ("유럽 연합 비자로 여러 나라를 동시에 여행할 수 있나요?",     CAT_CROSS, ["exception_handler"], None),
    ("비자 런을 하면 어떤 법적 문제가 생길 수 있나요?",          CAT_CROSS, ["exception_handler"], None),
    ("여권 유효기간이 6개월 미만이면 비자 신청이 가능한가요?",    CAT_CROSS, ["exception_handler"], None),
    ("범죄경력이 있으면 비자가 거절될 수 있나요?",               CAT_CROSS, ["exception_handler"], None),
    ("오버스테이 기록이 있어도 재입국이 가능한가요?",             CAT_CROSS, ["exception_handler"], None),
    ("여러 나라의 비자를 동시에 소지하는 것이 가능한가요?",       CAT_CROSS, ["exception_handler"], None),
    ("불법체류 전과가 있는데 다시 입국 신청이 가능한가요?",       CAT_CROSS, ["exception_handler"], None),
    ("환승비자 없이 국제공항 대기가 가능한 나라가 있나요?",       CAT_CROSS, ["exception_handler"], None),
    ("DUI 전과가 있는데 미국 입국이 가능한가요?",                 CAT_CROSS, ["exception_handler"], None),
    ("여권 유효기간이 3개월밖에 안 남았는데 비자 신청이 가능한가요?", CAT_CROSS, ["exception_handler"], None),
    ("임신 중인데 비자 신청을 해도 문제없나요?",                  CAT_CROSS, ["exception_handler"], None),
    ("동성 커플인데 비자 신청 시 차별을 받을 수 있나요?",         CAT_CROSS, ["exception_handler"], None),
    ("특정 종교를 가진 사람도 모든 나라에서 비자를 받을 수 있나요?", CAT_CROSS, ["exception_handler"], None),
]

BASIC_LONG_STAY = [
    # 15개 / 기대 노드: visa_rag_search
    ("캐나다에서 영구 주민(PR)이 되고 싶어요",                   CAT_LONG, ["visa_rag_search"], None),
    ("독일 블루카드로 장기 체류가 가능한가요?",                   CAT_LONG, ["visa_rag_search"], None),
    ("미국 EB-5 투자이민으로 영주권을 받을 수 있나요?",          CAT_LONG, ["visa_rag_search"], None),
    ("호주 영주권 신청 조건이 무엇인가요?",                       CAT_LONG, ["visa_rag_search"], None),
    ("싱가포르에서 장기 거주하려면 어떤 비자가 필요한가요?",      CAT_LONG, ["visa_rag_search"], None),
    ("영국 점수제 비자로 영주권을 받을 수 있나요?",              CAT_LONG, ["visa_rag_search"], None),
    ("뉴질랜드 영주권 신청 조건과 절차를 알려주세요",             CAT_LONG, ["visa_rag_search"], None),
    ("프랑스로 이민하려면 어떻게 해야 하나요?",                   CAT_LONG, ["visa_rag_search"], None),
    ("일본에서 경영관리 비자로 장기 체류가 가능한가요?",          CAT_LONG, ["visa_rag_search"], None),
    ("남아공으로 이민하는 조건은 어떻게 되나요?",                 CAT_LONG, ["visa_rag_search"], None),
    ("태국에서 장기 거주비자를 받을 수 있나요?",                  CAT_LONG, ["visa_rag_search"], None),
    ("말레이시아 이민 조건과 절차를 알려주세요",                  CAT_LONG, ["visa_rag_search"], None),
    ("포르투갈 골든비자로 영주권 취득이 가능한가요?",             CAT_LONG, ["visa_rag_search"], None),
    ("스페인으로 이민하는 방법은 무엇인가요?",                    CAT_LONG, ["visa_rag_search"], None),
    ("아일랜드에서 장기 거주하려면 어떤 비자가 필요한가요?",      CAT_LONG, ["visa_rag_search"], None),
]

BASIC_DEEP_SEARCH = [
    # 15개 / 기대 노드: web_search_tool
    # 반드시 DEEP_SEARCH_KEYWORDS 포함 (공식 사이트/상세 탐색/원문/이민청 등)
    ("프랑스 공식 사이트 상세 탐색으로 취업비자 최신 요건 알려줘",    CAT_DEEP, ["web_search_tool"], None),
    ("미국 USCIS 공식 사이트에서 I-129 폼 원문으로 설명해줘",        CAT_DEEP, ["web_search_tool"], None),
    ("호주 이민국 공식 사이트 상세 탐색 기술이민 조건을 알려줘",      CAT_DEEP, ["web_search_tool"], None),
    ("캐나다 이민청 공식 사이트 익스프레스 엔트리 점수 기준 원문",    CAT_DEEP, ["web_search_tool"], None),
    ("영국 gov.uk 상세 탐색 Tier 2 비자 최신 정보는?",               CAT_DEEP, ["web_search_tool"], None),
    ("독일 공식 이민국 기준 블루카드 요건을 알려줘",                  CAT_DEEP, ["web_search_tool"], None),
    ("일본 이민청 공식 기준 취업비자 요건을 원문으로 알려줘",         CAT_DEEP, ["web_search_tool"], None),
    ("싱가포르 MOM 공식 사이트 상세 탐색 비자 조건 알려줘",          CAT_DEEP, ["web_search_tool"], None),
    ("뉴질랜드 이민청 공식 영주권 신청 요건 상세 탐색",               CAT_DEEP, ["web_search_tool"], None),
    ("남아공 이민국 공식 정보로 취업비자 기준 알려줘",                CAT_DEEP, ["web_search_tool"], None),
    ("태국 공식 사이트 상세 탐색 장기거주비자 조건",                  CAT_DEEP, ["web_search_tool"], None),
    ("말레이시아 이민부 공식 기준 비자 조건 원문",                    CAT_DEEP, ["web_search_tool"], None),
    ("포르투갈 공식 사이트 골든비자 점수 기준 상세 탐색",             CAT_DEEP, ["web_search_tool"], None),
    ("브라질 공식 이민청 원문으로 취업비자 조건 알려줘",              CAT_DEEP, ["web_search_tool"], None),
    ("인도 공식 기준 기술비자 점수 산정 방법 원문",                   CAT_DEEP, ["web_search_tool"], None),
]

BASIC_REACTION = [
    # 15개 / 기대 노드: general_chat (감탄·반응·인사 — 비자 도메인 없음)
    ("뭐야 완전히 로또잖아;",                                    CAT_REACTION, ["general_chat"], None),
    ("진짜요? 신기하네요!",                                      CAT_REACTION, ["general_chat"], None),
    ("ㅋㅋㅋㅋ 말도 안 돼",                                     CAT_REACTION, ["general_chat"], None),
    ("대박!!!",                                                  CAT_REACTION, ["general_chat"], None),
    ("감사합니다!",                                              CAT_REACTION, ["general_chat"], None),
    ("정말 고마워요",                                            CAT_REACTION, ["general_chat"], None),
    ("아 알겠습니다",                                            CAT_REACTION, ["general_chat"], None),
    ("ok 감사합니다",                                            CAT_REACTION, ["general_chat"], None),
    ("좋아요!",                                                  CAT_REACTION, ["general_chat"], None),
    ("맞아요, 감사해요",                                         CAT_REACTION, ["general_chat"], None),
    ("헐!",                                                      CAT_REACTION, ["general_chat"], None),
    ("와!",                                                      CAT_REACTION, ["general_chat"], None),
    ("완전 신기해요",                                            CAT_REACTION, ["general_chat"], None),
    ("너무 고마워요",                                            CAT_REACTION, ["general_chat"], None),
    ("ㅎㄷㄷ 진짜요?",                                          CAT_REACTION, ["general_chat"], None),
]

BASIC_OFFTOPIC = [
    # 15개 / 기대 노드: general_chat (순수 잡담)
    ("오늘 날씨가 어때요?",                                      CAT_OFFTOPIC, ["general_chat"], None),
    ("점심에 뭐 먹을까요?",                                      CAT_OFFTOPIC, ["general_chat"], None),
    ("강남 맛집 추천해줘",                                       CAT_OFFTOPIC, ["general_chat"], None),
    ("파이썬 배우고 싶어요",                                     CAT_OFFTOPIC, ["general_chat"], None),
    ("영어 발음 좋아지는 방법은?",                               CAT_OFFTOPIC, ["general_chat"], None),
    ("주식 투자 어떻게 시작하나요?",                             CAT_OFFTOPIC, ["general_chat"], None),
    ("날씨 정말 좋네요",                                         CAT_OFFTOPIC, ["general_chat"], None),
    ("코딩 처음 어떻게 배웠어요?",                               CAT_OFFTOPIC, ["general_chat"], None),
    ("영어 공부 방법을 알려주세요",                              CAT_OFFTOPIC, ["general_chat"], None),
    ("게임 추천해줘",                                            CAT_OFFTOPIC, ["general_chat"], None),
    ("영화 뭐 볼까요?",                                         CAT_OFFTOPIC, ["general_chat"], None),
    ("책 추천해줘",                                              CAT_OFFTOPIC, ["general_chat"], None),
    ("헬스 시작하려는데 팁이 있나요?",                           CAT_OFFTOPIC, ["general_chat"], None),
    ("요리 레시피 알려줘",                                       CAT_OFFTOPIC, ["general_chat"], None),
    ("국내 여행지 추천해줘",                                     CAT_OFFTOPIC, ["general_chat"], None),
]

BASIC_NEW_COUNTRY = [
    # 15개 / 기대 노드: visa_rag_search (RAG 없으면 web_search_tool로 폴백 — 둘 다 PASS)
    ("남아공에서 취업하고 싶어요",                               CAT_NEWCOUNTRY, ["visa_rag_search", "web_search_tool"], None),
    ("인도에서 기술자 비자를 받을 수 있나요?",                   CAT_NEWCOUNTRY, ["visa_rag_search", "web_search_tool"], None),
    ("태국 장기 거주 비자가 있나요?",                            CAT_NEWCOUNTRY, ["visa_rag_search", "web_search_tool"], None),
    ("브라질에서 디지털 노마드 비자가 있나요?",                  CAT_NEWCOUNTRY, ["visa_rag_search", "web_search_tool"], None),
    ("말레이시아에서 일하고 싶어요",                             CAT_NEWCOUNTRY, ["visa_rag_search", "web_search_tool"], None),
    ("아랍에미리트에서 취업할 수 있나요?",                       CAT_NEWCOUNTRY, ["visa_rag_search", "web_search_tool"], None),
    ("포르투갈에 장기 거주하고 싶어요",                          CAT_NEWCOUNTRY, ["visa_rag_search", "web_search_tool"], None),
    ("스페인에서 취업하려면 어떻게 해야 하나요?",                CAT_NEWCOUNTRY, ["visa_rag_search", "web_search_tool"], None),
    ("이탈리아 유학비자 조건은 무엇인가요?",                     CAT_NEWCOUNTRY, ["visa_rag_search", "web_search_tool"], None),
    ("네덜란드에서 일하고 싶어요",                               CAT_NEWCOUNTRY, ["visa_rag_search", "web_search_tool"], None),
    ("스웨덴 취업비자는 어떻게 받나요?",                         CAT_NEWCOUNTRY, ["visa_rag_search", "web_search_tool"], None),
    ("덴마크에서 유학하고 싶어요",                               CAT_NEWCOUNTRY, ["visa_rag_search", "web_search_tool"], None),
    ("핀란드에서 일하고 싶어요",                                 CAT_NEWCOUNTRY, ["visa_rag_search", "web_search_tool"], None),
    ("노르웨이 거주비자 조건은 어떻게 되나요?",                  CAT_NEWCOUNTRY, ["visa_rag_search", "web_search_tool"], None),
    ("아일랜드에서 취업하고 싶어요",                             CAT_NEWCOUNTRY, ["visa_rag_search", "web_search_tool"], None),
]

# 기본 150개 합산
BASIC_150 = (
    BASIC_EMPLOYMENT +
    BASIC_STUDY +
    BASIC_EXTENSION +
    BASIC_STATUS_CHANGE +
    BASIC_CROSS_RULE +
    BASIC_LONG_STAY +
    BASIC_DEEP_SEARCH +
    BASIC_REACTION +
    BASIC_OFFTOPIC +
    BASIC_NEW_COUNTRY
)
assert len(BASIC_150) == 150, f"기본 케이스 수 오류: {len(BASIC_150)}"


# ══════════════════════════════════════════════════════════════════════════════
# 특수 30개
# ══════════════════════════════════════════════════════════════════════════════

SPECIAL_MULTITURN = [
    # 7개 / 이전 대화 맥락 포함 — 맥락 인계 및 수정 신호 처리 검증
    (
        "호주는 어떤가요?",
        CAT_MULTITURN,
        ["visa_rag_search"],
        [
            {"role": "user",      "content": "캐나다에서 개발자로 취업하고 싶어요"},
            {"role": "assistant", "content": "캐나다 IT 취업 비자는 익스프레스 엔트리가 주요 경로입니다."},
        ],
    ),
    (
        "아니 사실은 유학만 하고 싶어요",
        CAT_MULTITURN,
        ["visa_rag_search"],        # 수정 신호 후 유학으로 재라우팅
        [
            {"role": "user",      "content": "캐나다에서 취업"},
            {"role": "assistant", "content": "캐나다 취업비자 정보입니다."},
        ],
    ),
    (
        "그럼 영국 학생비자는 어떤가요?",
        CAT_MULTITURN,
        ["visa_rag_search"],        # 국가 변경 + 이전 목적(유학) 인계
        [
            {"role": "user",      "content": "미국 유학"},
            {"role": "assistant", "content": "미국 F1 비자 정보입니다."},
        ],
    ),
    (
        "3개월만 더 머물고 싶은데 가능한가요?",
        CAT_MULTITURN,
        ["exception_handler"],      # 체류 연장 요청
        [
            {"role": "user",      "content": "미국 관광비자로 6개월 체류 중"},
            {"role": "assistant", "content": "미국 관광비자는 보통 6개월입니다."},
        ],
    ),
    (
        "다시 생각해보니 취업보다 유학이 나을 것 같아요",
        CAT_MULTITURN,
        ["visa_rag_search"],        # 목적 수정 → 유학
        [
            {"role": "user",      "content": "캐나다 취업비자에 관심 있어요"},
            {"role": "assistant", "content": "캐나다 취업비자 정보입니다."},
        ],
    ),
    (
        "미안해요, 일자리를 구하려고 해요",
        CAT_MULTITURN,
        ["visa_rag_search"],        # 목적 수정 → 취업
        [
            {"role": "user",      "content": "유학에 관심이 있어요"},
            {"role": "assistant", "content": "유학 비자 정보입니다."},
        ],
    ),
    (
        "사실은 장기 체류가 목적이에요",
        CAT_MULTITURN,
        ["visa_rag_search"],        # 목적 수정 → 장기체류
        [
            {"role": "user",      "content": "단기 여행으로 가려고요"},
            {"role": "assistant", "content": "단기 여행 비자 정보입니다."},
        ],
    ),
]

SPECIAL_CONFLICTING = [
    # 8개 / 상충 신호 — 마지막 명시적 신호 우선
    ("미국에서 관광비자가 아니라 취업비자로 일하고 싶어요",       CAT_CONFLICT, ["exception_handler", "visa_rag_search"], None),
    ("유학이 아니라 취업으로 가고 싶어요",                        CAT_CONFLICT, ["exception_handler", "visa_rag_search"], None),
    ("워킹홀리데이가 아닌 정규직 취업비자를 원해요",              CAT_CONFLICT, ["visa_rag_search"],                    None),
    ("장기 체류가 아니라 단기 여행이에요",                        CAT_CONFLICT, ["visa_rag_search"],                    None),
    ("그게 아니고 다른 나라로 갈 수도 있어요",                   CAT_CONFLICT, ["response_formatter"],                 None),
    ("미국도 아니고 캐나다도 아니고 어느 나라든 괜찮아요",        CAT_CONFLICT, ["response_formatter"],                 None),
    ("취업도 아니고 유학도 아닌 다른 목적이에요",                 CAT_CONFLICT, ["response_formatter"],                 None),
    ("관광으로 입국 후 현지에서 취업을 원해요",                   CAT_CONFLICT, ["exception_handler"],                  None),
]

SPECIAL_VAGUE = [
    # 7개 / 도메인 신호 없는 모호 질문
    # response_formatter = 재질문으로 가는 것이 올바른 경로
    # general_chat = 비자 무관으로 분류(수용 가능)
    ("비자 받으려면 어떻게 해야 하나요?",                        CAT_VAGUE, ["response_formatter", "visa_rag_search"],  None),
    ("필요한 서류가 뭔가요?",                                    CAT_VAGUE, ["response_formatter"],                     None),
    ("시간이 얼마나 걸리나요?",                                  CAT_VAGUE, ["response_formatter", "general_chat"],     None),
    ("비용은 얼마예요?",                                         CAT_VAGUE, ["response_formatter", "general_chat"],     None),
    ("언제쯤 신청해야 하나요?",                                  CAT_VAGUE, ["response_formatter", "general_chat"],     None),
    ("어떻게 하면 되나요?",                                      CAT_VAGUE, ["response_formatter", "general_chat"],     None),
    ("최근에 바뀐 내용이 있나요?",                               CAT_VAGUE, ["response_formatter", "general_chat"],     None),
]

SPECIAL_EDGE = [
    # 8개 / 특수 신분·상황 — 비자 도메인이지만 이례적 케이스
    ("DUI 전과가 있는데 미국 입국이 가능한가요?",                 CAT_EDGE, ["exception_handler"],                      None),
    ("임신 중인데 비자 신청을 해도 문제없나요?",                  CAT_EDGE, ["exception_handler"],                      None),
    ("여권 유효기간이 3개월밖에 안 남았는데 비자 신청이 가능한가요?", CAT_EDGE, ["exception_handler"],                  None),
    ("동성 커플인데 비자 신청 시 차별을 받을 수 있나요?",         CAT_EDGE, ["exception_handler", "response_formatter"], None),
    ("코로나 확진 기록이 있어도 입국에 문제없나요?",              CAT_EDGE, ["response_formatter", "exception_handler"], None),
    ("범죄 경력이 있으면 비자 거절이 확실한가요?",               CAT_EDGE, ["exception_handler"],                       None),
    ("특정 종교로 인해 비자 거절 가능성이 있나요?",              CAT_EDGE, ["response_formatter", "exception_handler"], None),
    ("성소수자인데 특정 국가 입국이 가능한가요?",                 CAT_EDGE, ["exception_handler"],                       None),
]

# 특수 30개 합산
SPECIAL_30 = (
    SPECIAL_MULTITURN +
    SPECIAL_CONFLICTING +
    SPECIAL_VAGUE +
    SPECIAL_EDGE
)
assert len(SPECIAL_30) == 30, f"특수 케이스 수 오류: {len(SPECIAL_30)}"


# ══════════════════════════════════════════════════════════════════════════════
# 전체 180개
# ══════════════════════════════════════════════════════════════════════════════
ALL_180 = BASIC_150 + SPECIAL_30
assert len(ALL_180) == 180, f"전체 케이스 수 오류: {len(ALL_180)}"


# ── 카테고리 메타데이터 ────────────────────────────────────────────────────────
CATEGORY_META = {
    CAT_EMPLOYMENT:  {"label": "취업비자",        "type": "기본", "count": 15},
    CAT_STUDY:       {"label": "유학비자",         "type": "기본", "count": 15},
    CAT_EXTENSION:   {"label": "체류기간 연장",    "type": "기본", "count": 15},
    CAT_STATUS:      {"label": "신분 변경",        "type": "기본", "count": 15},
    CAT_CROSS:       {"label": "교차규칙",         "type": "기본", "count": 15},
    CAT_LONG:        {"label": "장기체류/영주",    "type": "기본", "count": 15},
    CAT_DEEP:        {"label": "공식사이트 딥서치", "type": "기본", "count": 15},
    CAT_REACTION:    {"label": "감탄/반응/인사",   "type": "기본", "count": 15},
    CAT_OFFTOPIC:    {"label": "비자 무관 잡담",   "type": "기본", "count": 15},
    CAT_NEWCOUNTRY:  {"label": "신규 국가",        "type": "기본", "count": 15},
    CAT_MULTITURN:   {"label": "멀티턴 (맥락)",   "type": "특수", "count":  7},
    CAT_CONFLICT:    {"label": "상충 신호",        "type": "특수", "count":  8},
    CAT_VAGUE:       {"label": "모호 질문",        "type": "특수", "count":  7},
    CAT_EDGE:        {"label": "긴급·특수 케이스", "type": "특수", "count":  8},
}


if __name__ == "__main__":
    # 데이터셋 유효성 빠른 확인
    from collections import Counter
    cat_counts = Counter(c for _, c, _, _ in ALL_180)
    print(f"총 케이스: {len(ALL_180)}")
    print("\n카테고리별 케이스 수:")
    for cat, cnt in sorted(cat_counts.items()):
        meta = CATEGORY_META.get(cat, {})
        print(f"  [{meta.get('type','?'):2s}] {cat:15s}: {cnt:3d}개  ({meta.get('label','')})")

    # 기대 노드 유효성 확인
    valid_nodes = {
        "visa_rag_search", "exception_handler", "web_search_tool",
        "general_chat", "response_formatter", "knowledge_writer",
        "search_quality_gate", "query_refiner", "intent_classifier",
    }
    bad = [(i+1, msg, n) for i, (msg, _, expects, _) in enumerate(ALL_180)
           for n in expects if n not in valid_nodes]
    if bad:
        print(f"\n⚠️  유효하지 않은 노드 참조: {bad}")
    else:
        print("\n✅ 모든 기대 노드 유효 확인 완료")
