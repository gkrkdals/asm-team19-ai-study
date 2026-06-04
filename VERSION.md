# VERSION HISTORY — VisaGuide AI

> **README.md** 는 서비스 설명과 아키텍처 개요를 담습니다.  
> **이 파일(VERSION.md)** 은 릴리스별 변경 이력을 관리합니다.  
> 형식: [Keep a Changelog](https://keepachangelog.com/ko/1.0.0/) 참고 (Added / Changed / Fixed / Removed)

---

## [v0.10.0] — 2026-06-04 (Round 10 / 현재)

### Added
- **Frontend UI 7종 개선** (`ui/app.py`, `ui/styles.css`)
  - 헤더 + 워크플로우 토글 버튼 — `sticky` 고정으로 스크롤 시에도 항상 표시
  - 대화 목록 **스크롤 컨테이너** — 5개 초과 시 `max-height: 40vh` + 내부 스크롤 자동 적용
  - **대화 설정 버튼(⚙️) 위치 변경** — 사이드바 하단 expander → 각 대화 행의 삭제 버튼 좌측 인라인
  - **태그 시각적 연관성** — "└ 🏷" 접두로 소속 대화 명확히 표시 + 활성 대화 좌측 보더 강조
  - **예시 질문 위치 변경** — 사이드바 → 신규 대화 세션 채팅창 상단 2열 그리드 버튼
  - **후속 질문 칩 3열→2열** — 소형 화면에서 요소 불안정 현상 해소
  - 설정 패널 인라인 표시 (열기/닫기 토글, 저장/닫기 버튼)

- **ChromaDB 재검색 증명 검증 v50** (`tests/scenarios_chroma_v50.py`, `tests/run_chroma_v50.py`)
  - Phase A (20개): 이전 v180 개선 필요 영역 재검증
    - A1: status_change (8개) — 화살표·전환 키워드 명시
    - A2: multi_turn (6개) — 수정신호 + 맥락 리셋 재확인
    - A3: conflicting (6개) — 명시적 부정+목적 패턴
  - Phase B (30개): ChromaDB knowledge_writer → 재요청 시 RAG 재활용 증명
    - B1 (15개): 신규 국가 첫 요청 → `web_search_tool` + `knowledge_writer` 실행 확인
    - B2 (15개): 같은 국가 재요청 → `visa_rag_search`로 직접 응답 (웹검색 생략) 확인
  - 실행기: `B1 → 3초 대기 → B2` 순서 보장, ChromaDB 재활용률 별도 리포트

- **ChromaDB 자가학습 사이클 라이브 증명** (`tests/proof_chroma_cycle.py`)
  - DB 0건 상태의 진짜 신규 국가 4개(🇮🇸 IS · 🇱🇺 LU · 🇪🇪 EE · 🇺🇾 UY)로
    `신규국가 → 웹검색 → ChromaDB 저장 → 재요청 시 DB 추출` 전체 사이클을 before/after로 검증
  - **결과: 4/4 완전 증명** (학습 저장 4/4, 재요청 DB추출[웹검색 없음] 4/4)

- **VERSION.md** — README에서 변경 이력 분리, 독립 파일로 관리

### Changed
- `render_sidebar()` 에서 `example_queries` 파라미터 제거 (예시 질문을 채팅창으로 이동)
- `render_initial_greeting()` → `render_initial_greeting(example_queries)` 로 시그니처 변경
- `render_followups()` per_row: `3` → `2` (반응형 안정화)
- CSS `.block-container` padding-top: `1.0rem` → `0` (sticky 헤더와 겹침 방지)
- CSS 워크플로우 패널 sticky top: `.5rem` → `3.5rem` (헤더 높이 반영)

### Fixed
- **UI 변경 미반영 문제** — `ui/app.py`/`styles.css` 코드는 올바르게 저장됐으나 화면 미반영.
  - **근본 원인**: Streamlit이 **watchdog 모듈 미설치** 상태라 파일 watcher가 비활성/폴링.
    파일을 `cp`로 통째 교체(inode 변경)하자 변경 감지에 실패 → 전날 기동한 프로세스가
    옛 코드를 계속 서빙. (Streamlit 1.41.1 자체는 `st.container(key=)` 지원 — 코드는 정상)
  - **조치**: stale 프로세스 종료 후 재기동. Preview로 7종 수정 렌더 확인 완료.
  - **권장**: `pip install watchdog` 설치 시 이후 핫리로드 정상 작동.

### Validation Results (ChromaDB)
```
[라이브 사이클 증명] 신규국가 4개 — 4/4 완전 증명
  IS/LU/EE/UY: BEFORE 0건 → 1차요청(web_search+knowledge_writer)
             → AFTER 1건(+1) → 재요청(visa_rag only, 웹검색 없음)

[v50 배치 검증] 50개 — 22/50 (44.0%)
  B2_chroma_recall : 14/15 (93.3%) ← ChromaDB 재활용 확인
  A1_status_change :  6/8  (75.0%) ← v180 20% → 75% 개선
  A2_multi_turn    :  2/6  (33.3%) ← 개선 필요 (Priority 2 잔존)
  A3_conflicting   :  0/6  ( 0.0%) ← 개선 필요 (Priority 3 잔존)
  B1_first_request :  0/15 ( 0.0%) ← 시스템 정상. 15개국이 이미 학습 완료
                                     (이전 라운드 누적) → web_search 대신 RAG 직행

[ChromaDB 현황] 총 137 문서 = 사전적재 99 + 자가학습(origin=web_search) 38
```

> **핵심**: B1=0%는 결함이 아니라 **이미 38개 학습 문서가 누적돼 있다는 증거**.
> 진짜 신규 국가(0건)로 다시 검증하니 **사이클 4/4 완전 동작** 확인.

---

## [v0.9.0] — 2026-06-03 (Round 9 최종 검증)

### Added
- **180개 종합 검증 데이터셋** (`tests/scenarios_v180.py`)
  - 기본 150개: 10개 카테고리 × 15개
  - 특수 30개: multi_turn(7) + conflicting(8) + vague(7) + edge_case(8)
- **검증 실행기** (`tests/run_v180.py`) — API 배치 호출, 카테고리별 신뢰도 집계
- **Round 9 최종 검증 보고서** (`ROUND_9_FINAL_VALIDATION_REPORT.md`)

### Changed
- `EXCEPTION_KEYWORDS` 22개 확장: DUI, 임신, 여권 유효기간, 동성, 성소수자, 종교, 상태변경 등
- `DEEP_SEARCH_KEYWORDS` 15개 확장: "점수", "기준", "산정", "공식 기준", "이민국", "gov.uk", "uscis" 등
- `PURPOSE_KEYWORDS`: 익스프레스 엔트리, H1B, F1, 블루카드, EB-5 등 프로그램명 추가
- `COUNTRY_KEYWORDS`: 프로그램명 → 국가 추론 매핑 추가 (H1B→US, Tier2→GB 등)
- `intent.py` 화살표 regex: `(관광|학생|취업) → (취업|영주권)` 패턴 → `status_change` 분기
- `intent.py` 수정신호 regex: "아니", "사실은", "그게 아니라" → 이전 맥락 무시 + 현재 우선
- `sessions.py` `LastRunReq`: `followups: Optional[List[str]]` 필드 추가
- `ui/app.py` `render_followups()`: AI 추천 / 기본 추천 배지 분기
- `ui/styles.css` `.fu-basic` 클래스 추가

### Fixed
- Bug 2: AI 후속 칩이 백엔드에서 생성돼도 프론트엔드에 미반영 (followups 미저장)
  → `last_run` 에 `followups` 필드 저장 + 프론트엔드 렌더링 분기

### Validation Results (v180)
```
전체 신뢰도: 150/180 (83.3%)
완벽 달성 100%: deep_search, cross_rule, edge_case, reaction, vague, new_country
개선 필요: status_change(20%), multi_turn(42.9%), conflicting(50%)
```

---

## [v0.8.0] — 2026-06-02 (Round 8)

### Added
- **AI 후속 질문 칩 (동적 생성)**: 답변 후 `/chat/followups` 로 대화 맥락 기반 4개 후속 질문
  LLM 동적 생성 → 칩으로 노출, 클릭 시 자동 실행. `last_run` 에 저장해 새로고침 보존.
- **트레이스 그래프 가로/세로 반응형**: 공간 크기에 따라 LR/TB 자동 전환, 수동 토글 가능.
- **사용자 줌 컨트롤**: 트레이스 그래프 −/＋/맞춤/100% 줌 버튼.
- **종합 검증 (시나리오 A/B/C + 전체 노드)**: 9개 노드 전부 도달성 확인.

### Changed
- 워크플로우 패널 열기/닫기 토글 도입 (사이드바형, 모바일·데스크탑 공통)
- 트레이스 선택 노드/간선 강조 (글로우 + 다크 헤일로 + 최상위 z-index)

---

## [v0.7.0] — 2026-06-01 (Round 7)

### Added
- **세션별 RESTful 트레이스 (2a)**: `/{sid}/trace` 세션별 1:1 매핑 + 세션 필터 구독
- **통합 병렬 허브 (2b)**: `/trace` 전체 세션 상태 카드 + 세션별 상세 링크
- **백엔드 RESTful 세션 스토어**: `/sessions` CRUD API, `data/sessions.json` 영속화
- **세션 영속화 (URL ?sid=)**: 새로고침·재시작에도 대화 보존
- **세션 메타데이터**: 이름·한줄 설명·태그 편집·표시

### Added
- **공식 사이트 상세 탐색 (딥서치)**: `deep_search` 키워드 → RAG 건너뛰고 `web_search_tool`
  직행, Tavily `search_depth=advanced` + raw_content 원문 탐색

---

## [v0.6.0] — 2026-05-31 (Round 6)

### Added
- **후속 요청 제안 버튼 (ChatGPT식)**: 정적 4개 칩 (더 구체적으로 / 최신 정보 / 다른 비자 / 딥서치)
- **선택 노드/간선 강조 (글로우·상위 렌더)**: 실행 경로 노드 z-index 레이어링

---

## [v0.5.0] — 2026-05-30 (Round 5)

### Added
- **3-pane 프론트엔드 리디자인**: 좌 다크 사이드바 + 중앙 채팅 + 우 워크플로우 패널
- **데스크탑 트레이스 레이아웃**: 반응형 카드 그리드 (auto-fill, minmax 330px)
- **knowledge_writer 노드**: 웹검색 결과 신뢰도 good → ChromaDB upsert (점진적 지식 축적)
- **예외 시나리오 13→21종**: I-539, 신분변경, 긴급발급, 오버스테이, DUI, 디지털 노마드 등

### Changed
- 의도추출 키워드 폴백: LLM null → 메시지에서 직접 국가/목적 보강 (결정적 라우팅)
- 트레이스 그래프 z-index: 실행 경로 노드/화살표 최상위 렌더링

---

## [v0.4.0] — 2026-05-29 (Round 4)

### Added
- **멀티 채팅 세션**: ➕ 새 대화 생성·전환·삭제, 세션별 맥락 유지
- **Tavily 검색어 정제**: Korea 배제, 핵심 영어 쿼리 템플릿 (국가명+visa+requirements)
- **검색 신뢰도 게이트 (search_quality_gate)**: 공식 출처·내용량 평가
- **LLM 검색어 재생성 루프 (query_refiner)**: 신뢰도 poor → 한국어→영어 재생성 후 재검색

---

## [v0.3.0] — 2026-05-28 (Round 3)

### Added
- **장기 체류 비중 강화**: 영주권·정착 경로, 갱신/전환 조건 시스템 프롬프트 보강
- **교차 예외규칙 13종**: 쉥겐, 환승, ESTA/eTA, 유효기간≠체류, 복수입국 등 RAG 적재
- **전세계 국가 대응**: `search_hints.py` 우선 공식도메인·검색어 템플릿 (남아공, 프랑스 등)
- **일반 대화 분기 (general_chat)**: 비자 무관 질문 격리
- **멀티턴 맥락 이어받기**: 직전 대화 국가·목적·직업 이어받기 (국가 변경 시 초기화)
- **응답 토큰 스트리밍**: 최종 답변 실시간 타자기 효과 (Streamlit + /trace 공통)

---

## [v0.2.0] — 2026-05-27 (Round 2)

### Added
- **intent_classifier 강건화**: temperature=0, VISA_KEYWORDS 도메인 강제, 오판 차단
- **Streamlit ↔ /trace 실시간 연동**: 이벤트 버스 + 캐시 무효화 + 직전 실행 리플레이
- **실시간 트레이스 대시보드 (`/trace`)**: 2D DAG 그래프, 단계별 타임라인, 클릭 팝업

---

## [v0.1.0] — 2026-05-26 (초기 구현)

### Added
- FastAPI 백엔드 + LangGraph 워크플로우 초기 구현
- ChromaDB RAG: 6개국 78개 비자 문서 인덱싱
- Tavily 웹검색 연동 (6개국 외 폴백)
- Streamlit 채팅 UI (단일 세션)
- 노드: `intent_classifier` → `visa_rag_search` / `web_search_tool` → `response_formatter`
- 예외 처리: `exception_handler` (연장·변경·거절 3종)

---

## 개선 예정 (Backlog)

### Priority 1 — status_change 라우팅 수정
- **문제**: "A → B" 전환 패턴이 `exception_handler` 로 50% 미만 라우팅
- **해결**: `intent.py` 화살표 감지 후 `exception_handler` 직결 + `EXCEPTION_KEYWORDS` 보강
- **예상 효과**: 20% → 85%+

### Priority 2 — multi_turn 상태 리셋
- **문제**: 수정신호("아니", "사실은") 감지 후 `state` 완전 초기화 미흡
- **해결**: `_NEGATION_RE` 감지 시 `state.country/purpose/profession` 명시적 리셋
- **예상 효과**: 42.9% → 85%+

### Priority 3 — conflicting 신호 처리
- **문제**: "X가 아니라 Y" 패턴 50% 처리
- **해결**: 명시적 부정+목적 조합 키워드 추가 또는 regex 강화
- **예상 효과**: 50% → 70%+

### 기타
- `status_change` / `multi_turn` / `conflicting` 개선 후 v180 회귀 테스트 재실행
- ChromaDB 재활용률 모니터링 자동화 (주기적 학습 문서 quality 체크)
