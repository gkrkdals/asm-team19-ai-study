"""
knowledge/exceptions.py  –  비자 예외 규칙 지식베이스 (RAG용)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
비자 도메인에는 단일 비자 레코드만으로는 답할 수 없는 '교차 규칙·예외'가 존재한다.
예) "쉥겐 비자로 영국에 갈 수 있나?" → 불가. 쉥겐과 영국은 별개 제도.

이 모듈은 그런 예외 규칙을 구조화된 문서로 제공하여, RAG 시스템이
비자 레코드와 함께 검색·참조할 수 있게 한다.

각 규칙(ExceptionRule)은 RAG 청크 1개로 변환 가능:
  - id        : 고유 식별자
  - title     : 규칙 제목
  - category  : 분류 (schengen|transit|eta|duration|visa_run|...)
  - countries : 관련 국가 코드
  - rule      : 핵심 규칙 (한국어)
  - detail    : 상세 설명
  - keywords  : RAG 검색 키워드
  - severity  : 중요도 (critical|high|medium)
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict


@dataclass
class ExceptionRule:
    id:        str
    title:     str
    category:  str
    countries: list[str]
    rule:      str
    detail:    str
    keywords:  list[str] = field(default_factory=list)
    severity:  str = "high"   # critical | high | medium

    def to_rag_chunk(self) -> dict:
        """RAG 인덱싱용 dict 반환. text 필드는 임베딩 대상."""
        text = (
            f"[{self.title}] ({self.category})\n"
            f"규칙: {self.rule}\n"
            f"상세: {self.detail}\n"
            f"관련 국가: {', '.join(self.countries) if self.countries else '전체'}"
        )
        d = asdict(self)
        d["text"] = text
        d["doc_type"] = "exception_rule"
        return d


# ═════════════════════════════════════════════════════════════════════════════
#  예외 규칙 정의
# ═════════════════════════════════════════════════════════════════════════════

EXCEPTION_RULES: list[ExceptionRule] = [

    # ── 쉥겐 협약 ──────────────────────────────────────────────────────────
    ExceptionRule(
        id="schengen_scope",
        title="쉥겐 비자의 적용 범위",
        category="schengen",
        countries=["DE","FR","IT","ES","NL","CH","SE","NO","AT","PT","PL"],
        rule="쉥겐 단기비자(Type C) 1장으로 29개 쉥겐 회원국을 자유 이동할 수 있으나, "
             "비쉥겐 국가(영국·아일랜드 등)에는 사용할 수 없다.",
        detail="쉥겐 지역은 2024년 기준 29개국(루마니아·불가리아 포함). "
               "쉥겐 비자로 비쉥겐 EU 국가나 영국·아일랜드 입국 시 별도 비자가 필요하다. "
               "반대로 영국 비자로 쉥겐 지역에 입국할 수 없다.",
        keywords=["쉥겐","schengen","유럽 비자","비쉥겐","Type C","단기비자","EU"],
        severity="critical",
    ),
    ExceptionRule(
        id="schengen_90_180",
        title="쉥겐 90/180일 체류 규칙",
        category="duration",
        countries=["DE","FR","IT","ES","NL","CH","SE","NO","AT","PT","PL"],
        rule="쉥겐 지역 무비자/단기비자 체류는 '임의의 180일 중 최대 90일'로 제한된다.",
        detail="개별 국가가 아니라 쉥겐 전체를 합산한다. 예) 프랑스 60일 + 독일 40일 = 100일은 위반. "
               "180일은 롤링(rolling) 방식으로 계산되며, 출입국일 모두 체류일에 포함된다.",
        keywords=["90일","180일","체류 기간","쉥겐 계산","rolling","무비자 체류"],
        severity="critical",
    ),
    ExceptionRule(
        id="schengen_to_nonschengen",
        title="쉥겐→비쉥겐 이동 시 비자 필요",
        category="schengen",
        countries=["GB","IE","DE","FR"],
        rule="쉥겐 국가에서 비쉥겐 국가(영국·아일랜드·키프로스 등)로 이동하면 해당국 비자/허가가 별도로 필요하다.",
        detail="예) 독일(쉥겐)에서 영국으로 갈 때 쉥겐 비자는 무효. 영국 Standard Visitor 또는 ETA가 필요. "
               "아일랜드는 쉥겐이 아니지만 영국과 공동여행구역(CTA)을 형성한다.",
        keywords=["쉥겐","비쉥겐","영국 이동","아일랜드","별도 비자","환승"],
        severity="critical",
    ),

    # ── 영국-아일랜드 공동여행구역 ─────────────────────────────────────────
    ExceptionRule(
        id="uk_ireland_cta",
        title="영국-아일랜드 공동여행구역(CTA)",
        category="special_zone",
        countries=["GB","IE"],
        rule="영국과 아일랜드는 공동여행구역(CTA)을 형성하나, 제3국 국민에게 자동 상호 입국권을 주지 않는다.",
        detail="영국·아일랜드 시민은 상호 자유 이동 가능. 그러나 한국 등 제3국 국민은 "
               "영국 비자로 아일랜드에 입국할 수 없고(British Irish Visa Scheme 예외), 각각 비자가 필요하다.",
        keywords=["CTA","공동여행구역","영국 아일랜드","BIVS","상호 입국"],
        severity="high",
    ),

    # ── 전자여행허가(ESTA/eTA) ─────────────────────────────────────────────
    ExceptionRule(
        id="eta_is_not_visa",
        title="전자여행허가(ESTA/eTA)는 비자가 아니다",
        category="eta",
        countries=["US","CA","AU","GB"],
        rule="ESTA(미국)·eTA(캐나다)·ETA(호주 601)·ETA(영국)는 '비자'가 아닌 사전 입국 허가다.",
        detail="비자면제프로그램 대상 국적자만 신청 가능하며, 취업·장기체류 불가. "
               "미국 ESTA는 최대 90일, 캐나다 eTA는 항공 입국 시 필요. "
               "비자 거부 이력이 있으면 전자허가가 거부될 수 있어 정식 비자를 신청해야 한다.",
        keywords=["ESTA","eTA","ETA","전자여행허가","비자면제","VWP","무비자"],
        severity="high",
    ),

    # ── 환승 비자 ──────────────────────────────────────────────────────────
    ExceptionRule(
        id="transit_visa",
        title="환승(경유) 비자 필요 여부",
        category="transit",
        countries=["US","GB","DE","FR","CN","JP"],
        rule="국가별로 공항 환승 시에도 비자가 필요할 수 있다(미국은 환승도 C-1 비자 필요).",
        detail="미국은 국제선 환승만 해도 C-1 환승비자 또는 ESTA가 필요하다(TWOV 없음). "
               "쉥겐은 공항환승비자(A 비자)가 일부 국적에 필요. "
               "중국은 일부 도시에서 24/72/144시간 무비자 환승(TWOV) 제공.",
        keywords=["환승비자","경유","transit","C-1","TWOV","공항환승","144시간"],
        severity="high",
    ),

    # ── 비자런 / visa hopping ──────────────────────────────────────────────
    ExceptionRule(
        id="visa_run_restriction",
        title="비자런·연속 관광비자 제한",
        category="visa_run",
        countries=["TH","AU","GB","SG"],
        rule="단기 관광비자를 반복 갱신하며 사실상 거주하는 '비자런'은 거부·입국 거절 사유가 된다.",
        detail="호주는 Visitor→Student 연속 신청('visa hopping')을 2024년부터 제한. "
               "태국·싱가포르는 잦은 무비자 입국 시 입국심사에서 거절될 수 있다. "
               "장기 체류 목적이면 처음부터 해당 목적 비자를 신청해야 한다.",
        keywords=["비자런","visa run","visa hopping","관광비자 갱신","연속 입국"],
        severity="medium",
    ),

    # ── 워킹홀리데이 ───────────────────────────────────────────────────────
    ExceptionRule(
        id="working_holiday_constraints",
        title="워킹홀리데이 협정·연령·평생 1회 제한",
        category="working_holiday",
        countries=["AU","GB","DE","JP","CA"],
        rule="워킹홀리데이는 양자 협정국 국민만, 보통 18~30세(일부 35세), 평생 1회로 제한된다.",
        detail="호주 417/462는 조건 충족 시 최대 3회(연장)지만 대부분 국가는 1회성. "
               "한 고용주 밑 근무기간 제한(호주 6개월 등)이 있다. "
               "협정이 없는 국적은 신청 자체가 불가하다.",
        keywords=["워킹홀리데이","워홀","협정국","연령 제한","417","462","1회"],
        severity="medium",
    ),

    # ── 비자 유효기간 vs 체류 허가 ─────────────────────────────────────────
    ExceptionRule(
        id="validity_vs_stay",
        title="비자 유효기간 ≠ 체류 허가 기간",
        category="duration",
        countries=[],
        rule="비자 유효기간(입국 가능 기간)과 실제 체류 허가 기간(입국 후 머물 수 있는 기간)은 다르다.",
        detail="예) 미국 B-1/B-2는 비자 유효기간이 10년이어도, 1회 입국 시 체류 허가는 보통 6개월. "
               "입국 시 CBP/입국심사관이 실제 체류 허용 기간(I-94 등)을 결정한다. "
               "일본은 '사증(비자)'과 '재류자격'이 별개로, 재류기간이 실제 체류를 좌우한다.",
        keywords=["유효기간","체류 허가","I-94","재류자격","validity","duration of stay"],
        severity="high",
    ),

    # ── 단수/복수 입국 ─────────────────────────────────────────────────────
    ExceptionRule(
        id="single_multiple_entry",
        title="단수입국(single) vs 복수입국(multiple) 비자",
        category="entry",
        countries=[],
        rule="단수입국 비자는 1회 입국 후 소멸되며, 출국 후 재입국하려면 새 비자가 필요하다.",
        detail="쉥겐 단수비자로 입국 후 비쉥겐(영국)에 갔다가 다시 쉥겐으로 돌아오면 재입국 불가. "
               "복수입국(MULT) 비자가 필요하다. 비자 표면의 'ENTRIES' 항목을 확인해야 한다.",
        keywords=["단수입국","복수입국","single entry","multiple entry","재입국","MULT"],
        severity="high",
    ),

    # ── 복수국적 / 여권 선택 ───────────────────────────────────────────────
    ExceptionRule(
        id="dual_nationality_entry",
        title="복수국적자의 입국 여권 규칙",
        category="nationality",
        countries=["US","AU"],
        rule="복수국적자는 입국국이 인정하는 여권으로 입출국해야 하는 경우가 있다.",
        detail="미국 시민권자는 반드시 미국 여권으로 미국에 입국해야 한다. "
               "호주 시민권자는 호주 여권 또는 별도 등록이 필요. "
               "비자 신청 시 어느 국적 여권을 쓰느냐에 따라 비자 면제 여부가 달라진다.",
        keywords=["복수국적","이중국적","여권 선택","dual nationality","입국 여권"],
        severity="medium",
    ),

    # ── 무비자 협정의 함정 ─────────────────────────────────────────────────
    ExceptionRule(
        id="visa_free_purpose_limit",
        title="무비자 입국의 목적 제한",
        category="visa_free",
        countries=[],
        rule="무비자(비자 면제) 입국은 관광·단기상용에 한정되며, 취업·유학·장기체류는 불가하다.",
        detail="무비자로 입국해 현지에서 취업하거나 학업을 하면 불법. "
               "온라인 원격근무(디지털 노마드)도 국가에 따라 무비자 범위를 벗어날 수 있다. "
               "장기·취업 목적이면 반드시 해당 비자를 사전 취득해야 한다.",
        keywords=["무비자","비자 면제","목적 제한","관광","취업 불가","디지털 노마드"],
        severity="high",
    ),

    # ── 일본 사증 vs 재류자격 ──────────────────────────────────────────────
    ExceptionRule(
        id="japan_visa_vs_status",
        title="일본: 사증(査証)과 재류자격(在留資格)의 분리",
        category="special_system",
        countries=["JP"],
        rule="일본은 입국용 '사증(비자)'과 체류 목적·기간을 정하는 '재류자격'이 별개 제도다.",
        detail="사증은 입국 허가용이고, 실제 체류는 재류자격(留学·技術人文知識国際業務 등)이 결정한다. "
               "재류자격 인정증명서(COE)를 먼저 받고 사증을 신청하는 순서가 일반적이다. "
               "재류기간 갱신·변경은 출입국재류관리청(moj.go.jp/isa)에서 처리.",
        keywords=["일본 비자","사증","재류자격","COE","在留資格","재류기간"],
        severity="high",
    ),
]


# ═════════════════════════════════════════════════════════════════════════════
#  공개 함수
# ═════════════════════════════════════════════════════════════════════════════

def all_rules() -> list[ExceptionRule]:
    return EXCEPTION_RULES


def rules_for_country(country_code: str) -> list[ExceptionRule]:
    """특정 국가 관련 규칙 + 전체 적용(countries 빈 리스트) 규칙 반환."""
    code = country_code.upper()
    return [r for r in EXCEPTION_RULES if not r.countries or code in r.countries]


def rules_by_category(category: str) -> list[ExceptionRule]:
    return [r for r in EXCEPTION_RULES if r.category == category]


def to_rag_chunks() -> list[dict]:
    """전체 예외 규칙을 RAG 인덱싱용 dict 리스트로 변환."""
    return [r.to_rag_chunk() for r in EXCEPTION_RULES]
