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

    # ── 시나리오 B: 체류 연장 긴급 상황(미국 관광 I-539) ───────────────────
    ExceptionRule(
        id="us_b2_stay_extension",
        title="미국 관광(B-2) 체류 연장 — Form I-539",
        category="extension",
        countries=["US"],
        rule="미국 입국 후 체류 허가(I-94)가 만료되기 전에 USCIS에 Form I-539(체류기간 연장/신분유지)를 "
             "신청해야 한다. 코로나·질병·항공편 결항 등 불가피한 사유면 연장 가능성이 높다.",
        detail="관광/방문(B-1/B-2)으로 입국했으나 귀국이 어려우면, I-94 만료 '이전'에 I-539를 온라인 또는 우편으로 접수한다. "
               "① 현재 체류 자격·I-94 만료일 확인 → ② I-539 작성·증빙(연장 사유, 체류 비용 충당 능력, 귀국 의사) 제출 → "
               "③ 적시 접수 시 결정 전까지 합법 체류로 간주(불법체류 누적 정지). "
               "공식: USCIS I-539 안내 uscis.gov/i-539, 긴급 문의 USCIS Contact Center 1-800-375-5283. "
               "무단 초과체류는 향후 입국금지(3년/10년 바)로 이어질 수 있으니 만료 전 조치가 핵심.",
        keywords=["체류 연장","연장","I-539","i539","관광 비자","B-2","비자 만료","귀국을 못","귀국 못",
                  "돌아가지 못","출국을 못","코로나","항공편","오버스테이"],
        severity="critical",
    ),

    # ── 시나리오 C: 신분 변경(관광 → 현지 취업) ───────────────────────────
    ExceptionRule(
        id="tourist_to_work_change",
        title="관광 입국 후 현지 취업 — 신분(자격) 변경 원칙",
        category="status_change",
        countries=["JP","US","AU","GB","DE"],
        rule="관광·무비자로 입국한 상태에서 현지 취업 제의를 받아도, 대부분의 국가는 현지에서 곧바로 "
             "취업 비자로 변경(전환)하는 것을 제한한다. 원칙적으로 출국 후 본국에서 취업 비자를 새로 신청해야 한다.",
        detail="일본은 관광(단기체재)에서의 재류자격 변경을 원칙적으로 불허에 가깝게 운용한다 → 통상 일단 출국 후 "
               "재류자격인정증명서(COE)를 받아 취업사증(技術·人文知識·国際業務 등)을 신청한다. "
               "미국도 B-1/B-2에서 취업(H-1B 등)으로의 현지 신분변경은 'dual intent' 문제로 매우 제한적이다. "
               "필요 서류: 고용계약서/오퍼레터, 학위·경력 증명, 회사 등기/재정 서류, 여권. "
               "⚠️ 무비자/관광 상태에서 실제로 일하면 '불법 취업'으로 강제퇴거·재입국 금지 등 중대한 패널티를 받는다. "
               "반드시 정식 취업비자 취득 후 근로를 시작해야 한다.",
        keywords=["현지 취업","취업 제의","취업 제안","잡 오퍼","신분 변경","자격 변경","재류자격 변경",
                  "관광 입국","status change","불법 취업","취업비자 전환"],
        severity="critical",
    ),

    # ── 긴급·급행 비자 발급 ────────────────────────────────────────────────
    ExceptionRule(
        id="emergency_expedited_visa",
        title="긴급·급행(Expedite) 비자 발급",
        category="emergency",
        countries=[],
        rule="가족 사망·중병·긴급 출장 등 인도적/긴급 사유가 있으면 다수 국가가 긴급 예약(Emergency "
             "Appointment)·급행 처리(Expedite/Premium Processing)를 제공한다.",
        detail="미국: 비자 인터뷰 긴급 예약 신청 + USCIS Premium Processing(I-907, 특정 비자 15일 처리). "
               "영국: Priority/Super Priority Service로 처리 단축. 쉥겐: 일부 영사관이 긴급 사유 시 우선 심사. "
               "증빙(사망진단서·입원확인서·고용주 레터 등)을 제출해야 하며 발급을 보장하지는 않는다. "
               "반드시 해당 대사관/영사관 공식 안내(긴급예약 페이지)를 따른다.",
        keywords=["긴급 비자","긴급비자","긴급 발급","비자 긴급","긴급 신청","급행","expedite",
                  "premium processing","긴급 예약","emergency appointment","우선 처리","priority",
                  "응급","빨리 발급"],
        severity="high",
    ),

    # ── 불법체류(오버스테이) 패널티 ────────────────────────────────────────
    ExceptionRule(
        id="overstay_penalty",
        title="불법체류(오버스테이)의 입국금지 패널티",
        category="overstay",
        countries=["US","GB","DE","AU"],
        rule="허가된 체류기간을 넘겨 머무르면 향후 입국금지(entry ban)·비자 무효 등 불이익이 발생한다.",
        detail="미국은 불법체류 180일 초과 시 3년, 1년 초과 시 10년 입국금지(3/10년 바)가 적용된다. "
               "쉥겐은 초과체류 시 입국거부·재입국 금지 기록(SIS)이 남을 수 있다. 영국·호주도 자진 출국 여부에 따라 "
               "재입국 제한 기간이 달라진다. 초과체류가 불가피하면 만료 전에 연장(I-539 등)·자진신고로 "
               "합법성을 유지하는 것이 최선이다.",
        keywords=["불법체류","오버스테이","overstay","초과 체류","입국금지","재입국 금지","3년 바","10년 바",
                  "entry ban","강제출국"],
        severity="critical",
    ),

    # ── 유학생 교외 근로(아르바이트) 시간 제한 ─────────────────────────────
    ExceptionRule(
        id="student_work_hours",
        title="유학생의 교외 근로(아르바이트) 시간 제한",
        category="study",
        countries=["US","GB","CA","AU","DE","JP"],
        rule="학생 비자 소지자는 학기 중 주당 근로시간이 제한되며(통상 20시간 내외), 무단 초과 근로는 비자 위반이다.",
        detail="미국 F-1은 교내 주 20시간(방학 풀타임), 교외 근로는 CPT/OPT 등 사전 허가 필요. "
               "영국 학생비자는 학기 중 주 20시간, 캐나다는 2024년부터 교외 주 24시간 허용, 호주는 2주 48시간(학기 중). "
               "독일은 연 120일(풀타임)/240일(하프), 일본 '유학' 재류자격은 자격외활동허가로 주 28시간. "
               "한도 초과 시 자격취소·강제퇴거 위험.",
        keywords=["유학생 아르바이트","근로시간","주 20시간","주 28시간","파트타임","part-time",
                  "CPT","OPT","자격외활동","학생 비자 일"],
        severity="high",
    ),

    # ── 여권 잔여 유효기간 6개월 규칙 ──────────────────────────────────────
    ExceptionRule(
        id="passport_six_month_validity",
        title="여권 잔여 유효기간 6개월 규칙",
        category="passport",
        countries=[],
        rule="다수 국가가 입국·출국 시점 기준 여권 잔여 유효기간 6개월 이상을 요구한다(국가별 상이).",
        detail="동남아·중동 다수 국가는 '입국일 기준 6개월 이상' 유효기간을 요구한다. 쉥겐은 '출국 예정일+3개월 이상'. "
               "미국·영국은 체류기간 동안 유효하면 되는 경우가 많다. 여권 잔여기간이 부족하면 탑승 거부·입국 거부가 "
               "될 수 있어 사전 갱신이 안전하다.",
        keywords=["여권 유효기간","여권 잔여","6개월","passport validity","여권 갱신","유효기간 부족"],
        severity="medium",
    ),

    # ── 범죄경력·DUI 와 입국 거부(Inadmissibility) ─────────────────────────
    ExceptionRule(
        id="criminal_inadmissibility",
        title="범죄경력·음주운전(DUI)과 입국 거부(Inadmissibility)",
        category="admissibility",
        countries=["US","CA","AU"],
        rule="음주운전(DUI)·마약·폭력 등 범죄 기록이 있으면 비자 거부 또는 입국 거부(inadmissible) 사유가 될 수 있다.",
        detail="캐나다는 DUI를 중대 범죄로 보아 입국 거부될 수 있으며 '범죄 재활(Criminal Rehabilitation)' 또는 "
               "임시거주허가(TRP)가 필요할 수 있다. 미국은 도덕적 비행(CIMT) 관련 범죄 시 비자 거부·웨이버(I-601) 필요. "
               "호주는 character test(품성 요건)를 적용한다. ESTA/eTA 신청 시 범죄·비자거부 이력을 정확히 신고해야 하며, "
               "허위 기재는 영구 입국금지 사유다.",
        keywords=["범죄경력","전과","음주운전","DUI","입국 거부","inadmissible","품성 요건",
                  "criminal rehabilitation","웨이버","입국금지"],
        severity="high",
    ),

    # ── 원격근무·디지털 노마드 비자 ────────────────────────────────────────
    ExceptionRule(
        id="digital_nomad_remote",
        title="원격근무·디지털 노마드 비자",
        category="remote_work",
        countries=["PT","ES","DE","AE","TH"],
        rule="해외에서 본국 회사 업무를 원격으로 수행하려면 관광비자가 아닌 '디지털 노마드/원격근무 비자'가 "
             "필요한 경우가 많다.",
        detail="포르투갈(D8), 스페인, UAE, 태국(DTV), 독일(프리랜서/Freiberufler 비자) 등이 원격근무자용 체류 경로를 "
               "운영한다. 관광·무비자로 입국해 장기 원격근무를 하면 체류 목적 위반이 될 수 있다. "
               "보통 최소 소득 요건과 민간 의료보험을 요구한다.",
        keywords=["디지털 노마드","원격근무","remote work","재택","프리랜서","D8","DTV","노마드 비자","워케이션"],
        severity="medium",
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
