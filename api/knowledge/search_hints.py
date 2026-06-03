"""
countries/search_hints.py  –  비6개국 대상 Tavily 검색 가속 힌트
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
6개국(US/GB/CA/DE/JP/AU)은 countries/<code>.py에 정밀 URL이 등록돼 있다.
그 외 국가는 Tavily(웹 검색 API)로 즉석 탐색하는데, 무작정 검색하면
느리고 비공식 출처가 섞인다.

이 모듈은 국가별로:
  ① 우선 도메인(공식 출처) — Tavily의 include_domains 파라미터로 전달
  ② 우선 검색어 템플릿       — 정확도 높은 쿼리 생성
을 제공하여 검색 속도와 신뢰도를 높인다.

사용 예 (Tavily):
    from visa_pipeline.countries.search_hints import build_tavily_query
    q = build_tavily_query("FR", visa_keyword="work visa")
    # → {"query": "France official work visa types eligibility requirements",
    #     "include_domains": ["france-visas.gouv.fr", "service-public.fr"]}
"""
from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
#  국가별 공식 비자/이민 도메인 (우선 출처)
#  ISO 3166-1 alpha-2  →  공식 도메인 리스트 (신뢰도 순)
# ─────────────────────────────────────────────────────────────────────────────
OFFICIAL_DOMAINS: dict[str, list[str]] = {
    # ── 이미 정밀 등록된 6개국 (Tavily 폴백 시에도 활용 가능) ─────────────
    "US": ["travel.state.gov", "uscis.gov"],
    "GB": ["gov.uk"],
    "CA": ["canada.ca", "cic.gc.ca"],
    "DE": ["auswaertiges-amt.de", "make-it-in-germany.com", "bamf.de"],
    "JP": ["moj.go.jp", "mofa.go.jp"],
    "AU": ["immi.homeaffairs.gov.au", "homeaffairs.gov.au"],

    # ── 아시아 ────────────────────────────────────────────────────────────
    "KR": ["hikorea.go.kr", "mofa.go.kr", "immigration.go.kr"],   # 한국
    "CN": ["visaforchina.cn", "nia.gov.cn"],                       # 중국
    "SG": ["ica.gov.sg", "mom.gov.sg"],                            # 싱가포르
    "HK": ["immd.gov.hk"],                                         # 홍콩
    "TW": ["boca.gov.tw"],                                         # 대만
    "IN": ["indianvisaonline.gov.in", "mha.gov.in"],              # 인도
    "TH": ["thaievisa.go.th", "immigration.go.th"],               # 태국
    "VN": ["evisa.gov.vn", "immigration.gov.vn"],                 # 베트남
    "MY": ["imi.gov.my"],                                          # 말레이시아
    "ID": ["molina.imigrasi.go.id", "imigrasi.go.id"],           # 인도네시아
    "PH": ["immigration.gov.ph"],                                  # 필리핀
    "AE": ["icp.gov.ae", "gdrfad.gov.ae"],                        # UAE

    # ── 유럽 (쉥겐 + 비쉥겐) ─────────────────────────────────────────────
    "FR": ["france-visas.gouv.fr", "service-public.fr"],          # 프랑스
    "IT": ["vistoperitalia.esteri.it", "esteri.it"],             # 이탈리아
    "ES": ["exteriores.gob.es"],                                  # 스페인
    "NL": ["ind.nl", "netherlandsworldwide.nl"],                 # 네덜란드
    "CH": ["sem.admin.ch"],                                       # 스위스(비EU)
    "SE": ["migrationsverket.se"],                               # 스웨덴
    "NO": ["udi.no"],                                             # 노르웨이(비EU·쉥겐)
    "IE": ["irishimmigration.ie"],                               # 아일랜드(비쉥겐)
    "PT": ["aima.gov.pt", "vistos.mne.gov.pt"],                  # 포르투갈
    "AT": ["migration.gv.at"],                                    # 오스트리아
    "PL": ["udsc.gov.pl"],                                        # 폴란드

    # ── 아메리카 ──────────────────────────────────────────────────────────
    "MX": ["gob.mx"],                                             # 멕시코
    "BR": ["gov.br"],                                             # 브라질
    "AR": ["migraciones.gov.ar"],                                # 아르헨티나

    # ── 오세아니아 / 기타 ─────────────────────────────────────────────────
    "NZ": ["immigration.govt.nz"],                               # 뉴질랜드
    "ZA": ["dha.gov.za"],                                        # 남아공
}

# 국가별 한국어/영어 표기 (검색어 생성용)
COUNTRY_NAMES: dict[str, str] = {
    "KR": "South Korea", "CN": "China", "SG": "Singapore", "HK": "Hong Kong",
    "TW": "Taiwan", "IN": "India", "TH": "Thailand", "VN": "Vietnam",
    "MY": "Malaysia", "ID": "Indonesia", "PH": "Philippines", "AE": "UAE",
    "FR": "France", "IT": "Italy", "ES": "Spain", "NL": "Netherlands",
    "CH": "Switzerland", "SE": "Sweden", "NO": "Norway", "IE": "Ireland",
    "PT": "Portugal", "AT": "Austria", "PL": "Poland", "MX": "Mexico",
    "BR": "Brazil", "AR": "Argentina", "NZ": "New Zealand", "ZA": "South Africa",
}

# ─────────────────────────────────────────────────────────────────────────────
#  검색어 템플릿 (비자 카테고리별)
# ─────────────────────────────────────────────────────────────────────────────
QUERY_TEMPLATES: dict[str, str] = {
    "all":        "{country} official visa types list eligibility requirements",
    "work":       "{country} work visa eligibility requirements official",
    "student":    "{country} student visa requirements official immigration",
    "tourist":    "{country} tourist visitor visa requirements official",
    "family":     "{country} family reunion spouse visa official immigration",
    "immigration":"{country} permanent residence immigration official",
    "business":   "{country} business investor visa official requirements",
}


def build_tavily_query(country_code: str, visa_keyword: str = "all") -> dict:
    """
    Tavily 검색용 쿼리 + 우선 도메인을 생성한다.

    Parameters
    ----------
    country_code : ISO 2자리 코드 (예: "FR", "KR")
    visa_keyword : QUERY_TEMPLATES 키 또는 자유 키워드
                   ("all"|"work"|"student"|"tourist"|"family"|"immigration"|"business")

    Returns
    -------
    {
        "query":           str,        # Tavily query 파라미터
        "include_domains": list[str],  # Tavily include_domains 파라미터 (없으면 [])
        "country_code":    str,
        "is_known":        bool,       # 우선 도메인 보유 여부
    }
    """
    code = country_code.upper()
    name = COUNTRY_NAMES.get(code, code)
    domains = OFFICIAL_DOMAINS.get(code, [])

    template = QUERY_TEMPLATES.get(visa_keyword)
    if template:
        query = template.format(country=name)
    else:
        # 자유 키워드 — 국가명 + 키워드 + 공식 출처 유도
        query = f"{name} {visa_keyword} visa official immigration requirements"

    return {
        "query":           query,
        "include_domains": domains,
        "country_code":    code,
        "is_known":        bool(domains),
    }


def get_priority_domains(country_code: str) -> list[str]:
    """국가의 우선 공식 도메인 리스트 반환 (없으면 빈 리스트)."""
    return OFFICIAL_DOMAINS.get(country_code.upper(), [])


def list_supported_search_countries() -> list[str]:
    """우선 도메인이 등록된 전체 국가 코드."""
    return sorted(OFFICIAL_DOMAINS.keys())
