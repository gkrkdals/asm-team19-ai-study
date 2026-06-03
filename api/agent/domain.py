COUNTRY_KO = {
    "US": "미국", "JP": "일본", "GB": "영국",
    "CA": "캐나다", "AU": "호주", "DE": "독일",
}
PURPOSE_KO = {
    "employment": "취업", "study": "유학", "travel": "여행/관광",
    "long_stay": "장기체류", "working_holiday": "워킹홀리데이",
}
EXCEPTION_KO = {
    "extension": "체류 기간 연장",
    "status_change": "비자 신분 변경",
    "rejection": "비자 거절/재신청",
    "cross_rule": "교차 규칙(쉥겐·환승·전자여행허가 등)",
    "emergency": "긴급·급행 비자 발급",
}

# 국가명(한/영) → ISO 3166-1 alpha-2 코드. LLM 이 country=null 을 반환해도
# 메시지에서 직접 국가를 보강해 워크플로(visa_rag_search) 진입을 결정적으로 만든다.
# 더 긴 키가 먼저 매칭되도록 길이 내림차순으로 순회한다(아래 함수 참고).
COUNTRY_KEYWORDS = {
    # 프로그램명으로 국가 추론 (예: "익스프레스 엔트리" → CA)
    "익스프레스 엔트리": "CA", "express entry": "CA",
    "h1b": "US", "h-1b": "US", "l-1 비자": "US", "eb-5": "US", "uscis": "US",
    "tier 2": "GB", "tier 4": "GB",
    "blue card": "DE", "블루카드": "DE",
    # 6개국(정밀 RAG)
    "캐나다": "CA", "canada": "CA",
    "미국": "US", "united states": "US", "america": "US", "usa": "US",
    "일본": "JP", "japan": "JP",
    "영국": "GB", "united kingdom": "GB", "britain": "GB", "england": "GB",
    "호주": "AU", "오스트레일리아": "AU", "australia": "AU",
    "독일": "DE", "germany": "DE",
    # 글로벌(웹검색 폴백)
    "프랑스": "FR", "france": "FR",
    "남아공": "ZA", "남아프리카": "ZA", "south africa": "ZA",
    "중국": "CN", "china": "CN",
    "싱가포르": "SG", "singapore": "SG",
    "태국": "TH", "thailand": "TH",
    "베트남": "VN", "vietnam": "VN",
    "뉴질랜드": "NZ", "new zealand": "NZ",
    "네덜란드": "NL", "netherlands": "NL",
    "스페인": "ES", "spain": "ES",
    "이탈리아": "IT", "italy": "IT",
    "아일랜드": "IE", "ireland": "IE",
    "인도": "IN", "india": "IN",
    "필리핀": "PH", "philippines": "PH",
    "말레이시아": "MY", "malaysia": "MY",
    "인도네시아": "ID", "indonesia": "ID",
    "포르투갈": "PT", "portugal": "PT",
    "아랍에미리트": "AE", "두바이": "AE",
    "멕시코": "MX", "mexico": "MX",
    "브라질": "BR", "brazil": "BR",
}

# 체류 목적 키워드(한/영) → purpose. country 와 함께 있으면 visa_rag_search 로 진입.
# 더 구체적인 키를 앞에 둔다(예: '워킹홀리데이' 가 '취업/유학'보다 먼저 평가되도록).
PURPOSE_KEYWORDS = {
    "워킹홀리데이": "working_holiday", "워홀": "working_holiday", "working holiday": "working_holiday",
    "취업": "employment", "취직": "employment", "구직": "employment", "고용": "employment",
    "일자리": "employment", "직장": "employment", "근로": "employment", "노동": "employment",
    "잡 오퍼": "employment", "취업하": "employment", "일하": "employment", "work": "employment",
    # ② 추가: 프로그램명 직접 언급 (국가 없이도 목적 추출)
    "익스프레스 엔트리": "employment", "express entry": "employment",
    "h1b": "employment", "h-1b": "employment", "l1 비자": "employment", "l-1": "employment",
    "eb-5": "long_stay", "eb5": "long_stay",
    "블루카드": "employment", "blue card": "employment",
    "유학": "study", "어학연수": "study", "어학": "study", "학생": "study", "입학": "study",
    "공부": "study", "대학원": "study", "study": "study", "student": "study",
    "f1 비자": "study", "f-1": "study", "tier 4": "study",
    "여행": "travel", "관광": "travel", "여행자": "travel", "tourist": "travel",
    "이민": "long_stay", "영주": "long_stay", "정착": "long_stay", "장기체류": "long_stay",
    "이주": "long_stay", "거주": "long_stay", "immigration": "long_stay", "permanent": "long_stay",
    "영주권": "long_stay", "pr 비자": "long_stay",
}

# 비자 도메인 신호 키워드(휴리스틱). 하나라도 등장하면 비자 관련 질문으로 강제 분류해
# LLM 의 오판(예: "캐나다 취업"을 일반대화로 분류)을 방지한다.
VISA_KEYWORDS = [
    "비자", "visa", "사증", "여권", "passport",
    "취업", "고용", "일자리", "직장", "근로", "work permit", "워크퍼밋",
    "유학", "학생", "student", "어학", "입학",
    "여행", "관광", "tourist", "visit",
    "체류", "거주", "정착", "이민", "immigration", "영주", "permanent",
    "입국", "출국", "재입국", "환승", "경유", "transit",
    "워홀", "워킹홀리데이", "working holiday",
    "스폰서", "sponsor", "초청", "lmia", "coe",
    "장기체류", "단기체류", "esta", "eta", "쉥겐", "셴겐", "schengen",
    "해외", "외국", "현지", "대사관", "영사관", "이주",
]

EXCEPTION_KEYWORDS = {
    # ── 체류 기간 연장 ───────────────────────────────────────────────────────
    "연장": "extension", "기간 연장": "extension", "체류 연장": "extension",
    "만료": "extension", "expire": "extension",
    "i-539": "extension", "i539": "extension",
    "귀국을 못": "extension", "귀국 못": "extension", "귀국하지 못": "extension",
    "돌아가지 못": "extension", "출국을 못": "extension",
    # ② 새로 추가: "2년차/세컨드/second year" — 워홀 2차 연장 패턴
    "2년차": "extension", "2차": "extension", "세컨드": "extension", "second year": "extension",

    # ── 신분·비자 유형 변경 ──────────────────────────────────────────────────
    "신분 변경": "status_change", "비자 변경": "status_change", "자격 변경": "status_change",
    "status change": "status_change",
    "취업 제의": "status_change", "취업 제안": "status_change", "현지 취업": "status_change",
    "취업 권유": "status_change", "잡 오퍼": "status_change",
    # ② 추가: "전환/변경/→" 패턴 — "학생 → 취업", "관광 후 취업", "비자 유형 변경"
    # ⚠️ 주의: "전환 가능", "영주권 신청"처럼 광범위한 키워드는 포함하지 말 것
    #         (유학비자→취업 전환도 study 질문이 될 수 있음)
    "비자 전환": "status_change", "비자전환": "status_change",
    "종류 변경": "status_change", "유형 변경": "status_change",
    "관광 후 취업": "status_change", "관광 후 일": "status_change",
    "관광비자 후": "status_change", "관광 → 취업": "status_change",
    # "→ 취업" 단독은 너무 광범위 — arrow-regex 에서 처리(앞 맥락 필요)
    "→ 영주권": "status_change", "→ 유학비자": "status_change",
    "신분전환": "status_change", "신분 전환": "status_change",
    "비자 업그레이드": "status_change", "비자 업그레": "status_change",
    # "취업비자 → 영주권" — 비자 레코드 전환(status_change)
    "취업비자 →": "status_change", "취업 비자 →": "status_change",
    "비자에서 영주권": "status_change", "비자로 영주권": "status_change",

    # ── 비자 거절·재신청 ────────────────────────────────────────────────────
    "거절": "rejection", "재신청": "rejection", "거부": "rejection",
    "추방": "rejection", "deportation": "rejection",

    # ── 긴급·급행 발급 ───────────────────────────────────────────────────────
    "긴급 비자": "emergency", "긴급비자": "emergency", "급행": "emergency",
    "긴급 발급": "emergency", "비자 긴급": "emergency", "긴급 신청": "emergency",
    "expedite": "emergency", "premium processing": "emergency", "긴급 예약": "emergency",

    # ── 교차 규칙(단일 비자 레코드로 답할 수 없는 예외) ───────────────────────
    "쉥겐": "cross_rule", "셴겐": "cross_rule", "schengen": "cross_rule",
    "환승": "cross_rule", "경유": "cross_rule", "transit": "cross_rule",
    "비자런": "cross_rule", "비자 런": "cross_rule", "visa run": "cross_rule",
    "esta": "cross_rule", "eta": "cross_rule", "전자여행허가": "cross_rule",
    "복수국적": "cross_rule", "이중국적": "cross_rule",
    "단수입국": "cross_rule", "복수입국": "cross_rule",
    "불법체류": "cross_rule", "오버스테이": "cross_rule", "overstay": "cross_rule",
    # ② 새로 추가: 여권·여러 나라·DUI·오버스테이 변형
    "여권 유효기간": "cross_rule", "여권 만료": "cross_rule", "여권유효기간": "cross_rule",
    "여권 유효": "cross_rule", "여권기간": "cross_rule",
    "여러 나라": "cross_rule", "복수 국가": "cross_rule", "여러나라": "cross_rule",
    "유럽 연합": "cross_rule", "유럽연합": "cross_rule", "유럽 여러": "cross_rule",
    "범죄경력": "cross_rule", "범죄 경력": "cross_rule", "전과": "cross_rule",
    "dui": "cross_rule", "음주운전": "cross_rule",
    "입국 금지": "cross_rule", "입국금지": "cross_rule", "입국 거부": "cross_rule",
    "블랙리스트": "cross_rule", "3년 바": "cross_rule", "10년 바": "cross_rule",
    "근로 시간": "cross_rule", "근로시간": "cross_rule", "시간 제한": "cross_rule",

    # ④ Edge Cases 특수 상황(cross_rule 유형)
    # DUI/음주운전, 범죄경력, 임신, 질병 등 특수 신분
    "dui": "cross_rule", "음주운전": "cross_rule", "음주 운전": "cross_rule",
    "임신": "cross_rule", "임신했": "cross_rule", "임신 중": "cross_rule",
    "질병": "cross_rule", "확진": "cross_rule", "코로나": "cross_rule", "covid": "cross_rule",
    "여권 유효기간": "cross_rule", "여권기간": "cross_rule", "여권 6개월": "cross_rule",
    "동성": "cross_rule", "동성커플": "cross_rule", "lgbtq": "cross_rule",
    "성적지향": "cross_rule", "성소수자": "cross_rule",
    "차별": "cross_rule", "차별 당할": "cross_rule", "거절": "cross_rule",
    "종교": "cross_rule", "종교 신앙": "cross_rule",
}

# 공식 사이트 '상세 탐색'(딥서치) 트리거 키워드
DEEP_SEARCH_KEYWORDS = [
    "상세 탐색", "자세히 탐색", "상세히 탐색", "심층", "딥서치", "deep search",
    "공식 사이트", "공식사이트", "원문", "최신 정보로", "최신 정보 확인",
    # ③ 추가: 공식 기준/조건/이민국 명시
    "공식 기준", "공식 조건", "공식 요건", "공식 정보", "공식 사이트 정보",
    "이민국 기준", "이민국 조건", "기술이민 조건", "기술이민 기준",
    "점수 기준", "기준 점수", "공식 점수", "점수 산정", "점수", "산정 방법",
    # 공식 웹사이트 도메인·기관명
    "gov.uk", "uscis", ".gov", "mom", "immi.homeaffairs", "canada.ca",
    "vfs global", "france-visas", "뉴질랜드", "이민청", "이민국", "이민부",
]


def is_deep_search(message: str) -> bool:
    """공식 사이트 상세 탐색(Tavily advanced) 요청인지 판별."""
    msg = (message or "").lower()
    return any(k.lower() in msg for k in DEEP_SEARCH_KEYWORDS)


def detect_country(message: str) -> str | None:
    """메시지에서 국가명을 찾아 ISO alpha-2 코드를 반환(없으면 None). 긴 키 우선."""
    msg = (message or "").lower()
    for kw in sorted(COUNTRY_KEYWORDS, key=len, reverse=True):
        if kw.lower() in msg:
            return COUNTRY_KEYWORDS[kw]
    return None


def detect_purpose(message: str) -> str | None:
    """메시지에서 체류 목적 키워드를 찾아 purpose 를 반환(없으면 None). 긴 키 우선."""
    msg = (message or "").lower()
    for kw in sorted(PURPOSE_KEYWORDS, key=len, reverse=True):
        if kw.lower() in msg:
            return PURPOSE_KEYWORDS[kw]
    return None


SYSTEM_PROMPT = """당신은 VisaGuide AI입니다. 한국인 사용자의 해외 비자 정보를 안내하는 AI 어시스턴트입니다.

역할:
- 목적지 국가(미국·일본·영국·캐나다·호주·독일 + 그 외 국가는 웹검색), 체류 목적, 기간을 파악하여 적합한 비자를 추천합니다
- 비자 요건, 필요 서류, 처리 기간, 주의사항, 공식 링크를 안내합니다
- 체류 연장, 신분 변경, 비자 거절 후 재신청 등 예외 상황도 처리합니다
- 특히 '장기 체류(취업 이주·영주권·가족·정착)' 관점을 비중 있게 다룹니다: 단기 비자에서
  장기 체류·영주권으로 이어지는 경로(예: 취업→영주권, 유학→취업→정착)와 갱신·전환 조건을
  함께 안내합니다
- 쉥겐·환승·전자여행허가(ESTA/eTA)·유효기간≠체류기간 등 교차 예외규칙이 제공되면 반드시 반영합니다

톤앤매너:
- 친절하고 명확한 한국어로 법령 용어는 쉽게 풀어 설명합니다
- 단정적 법적 판단은 하지 않으며 '참고 정보'임을 명시합니다
- 불확실한 정보는 솔직히 인정하고 공식 확인을 권장합니다
- 다음 단계 액션 아이템을 항상 제시합니다

제약:
- 실제 비자 신청 대행, 법적 해석, 승인 가능성 예측은 제공하지 않습니다"""
