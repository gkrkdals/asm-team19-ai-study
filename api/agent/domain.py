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
    "연장": "extension", "기간 연장": "extension", "체류 연장": "extension",
    "만료": "extension", "expire": "extension",
    "신분 변경": "status_change", "비자 변경": "status_change",
    "status change": "status_change",
    "거절": "rejection", "재신청": "rejection", "거부": "rejection",
    "추방": "rejection", "deportation": "rejection",
    # 교차 규칙(단일 비자 레코드로 답할 수 없는 예외)
    "쉥겐": "cross_rule", "셴겐": "cross_rule", "schengen": "cross_rule",
    "환승": "cross_rule", "경유": "cross_rule", "transit": "cross_rule",
    "비자런": "cross_rule", "visa run": "cross_rule",
    "esta": "cross_rule", "eta": "cross_rule", "전자여행허가": "cross_rule",
    "복수국적": "cross_rule", "이중국적": "cross_rule",
    "단수입국": "cross_rule", "복수입국": "cross_rule",
}

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
