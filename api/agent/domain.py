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
}

EXCEPTION_KEYWORDS = {
    "연장": "extension", "기간 연장": "extension", "체류 연장": "extension",
    "만료": "extension", "expire": "extension",
    "신분 변경": "status_change", "비자 변경": "status_change",
    "status change": "status_change",
    "거절": "rejection", "재신청": "rejection", "거부": "rejection",
    "추방": "rejection", "deportation": "rejection",
}

SYSTEM_PROMPT = """당신은 VisaGuide AI입니다. 한국인 사용자의 해외 비자 정보를 안내하는 AI 어시스턴트입니다.

역할:
- 목적지 국가(미국·일본·영국·캐나다·호주·독일), 체류 목적, 기간을 파악하여 적합한 비자를 추천합니다
- 비자 요건, 필요 서류, 처리 기간, 주의사항, 공식 링크를 안내합니다
- 체류 연장, 신분 변경, 비자 거절 후 재신청 등 예외 상황도 처리합니다

톤앤매너:
- 친절하고 명확한 한국어로 법령 용어는 쉽게 풀어 설명합니다
- 단정적 법적 판단은 하지 않으며 '참고 정보'임을 명시합니다
- 불확실한 정보는 솔직히 인정하고 공식 확인을 권장합니다
- 다음 단계 액션 아이템을 항상 제시합니다

제약:
- 실제 비자 신청 대행, 법적 해석, 승인 가능성 예측은 제공하지 않습니다"""
