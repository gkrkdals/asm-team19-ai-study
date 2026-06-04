# 🛂 VisaGuide AI

목적·기간·상황에 따라 최적의 해외 비자를 AI가 탐색·추천해 주는 **Agentic 정보 서비스** (프로토타입).

> "어느 나라에서, 얼마나, 무슨 목적으로?" — 세 가지 입력만으로 필요한 비자 정보를 즉시 안내하는 한국어 AI 챗봇

지원 국가: 🇺🇸 미국 · 🇯🇵 일본 · 🇬🇧 영국 · 🇨🇦 캐나다 · 🇦🇺 호주 · 🇩🇪 독일 (총 78개 비자 데이터)

---

## 기술 스택

| 레이어 | 기술 |
|---|---|
| Frontend | 정적 SPA (Express 정적 서버 `web/`, :3000) — `web/public/app.html` |
| Backend API | FastAPI (순수 REST/SSE API) |
| Agent Orchestration | LangGraph (노드/엣지 기반 워크플로우) |
| LLM | Upstage Solar (`solar-pro`) / OpenAI 대체 가능 |
| RAG | ChromaDB (벡터 검색, 코사인 유사도) |
| Tool Calling | Tavily Search API (공식 사이트 실시간 검색) |
| Infra | Docker Compose |

## LangGraph Agentic Workflow

```
intent_classifier ─┬─ (비자 무관) ───────→ general_chat ─────────────────────────────→ END
                   ├─ (예외/교차규칙) ───→ exception_handler ─────────────────→ response_formatter ─→ END
                   ├─ (국가+목적) ──────→ visa_rag_search ─┬─ (비자 결과 O) ─→ response_formatter ─→ END
                   │                                       └─ (결과 X) ─→ web_search_tool → search_quality_gate
                   │                                                            ↑                  │
                   │                                              query_refiner ┘  (신뢰도 낮음·재시도)│
                   │                                  (신뢰도 충분) → knowledge_writer(ChromaDB 학습 저장) ─→ response_formatter
                   └─ (정보 부족) ─────────────────────────────────────────────────────→ response_formatter (재질문)
```

- **intent_classifier**: 국가(ISO 코드)·목적·기간·직업 추출 + **비자 관련 여부 판별** + 예외 키워드(연장/변경/거절·**쉥겐/환승/ESTA** 등) 감지 + **멀티턴 맥락 이어받기**(이전 대화 반영)
- **general_chat**: 비자와 무관한 질문을 간단히 응대하고 도메인으로 유도 (노드 오진입 방지)
- **visa_rag_search**: ChromaDB 비자 문서 검색 + **교차 예외규칙(extra_context)** 병합
- **web_search_tool**: 6개국 외 국가까지 대응. `search_hints`의 **우선 공식도메인(include_domains)**·검색어 템플릿 적용
- **search_quality_gate**: 웹 결과 신뢰도(공식 출처 포함·내용량) 평가
- **query_refiner**: 신뢰도가 낮으면 **LLM이 한국어→영어 공식 검색어를 재생성**해 재검색(최대 2회 루프)
- **knowledge_writer**: 신뢰도 **good**인 웹 검색 결과를 **ChromaDB 비자 컬렉션에 학습 저장(upsert)** → 다음 동일 국가 질의 시 RAG로 즉시 활용(웹검색 생략). 이 동작은 트레이스에 `지식 학습 저장` 노드로 노출됩니다.
- **exception_handler**: 연장·변경·거절 + 쉥겐·환승·전자여행허가 + **체류연장(I-539)·관광→취업 신분변경·긴급발급·오버스테이** 등 **교차 규칙**을 키워드+의미 하이브리드로 검색
- **response_formatter**: 추천 비자/요건/서류/주의사항/공식 링크 구조화 (**토큰 스트리밍**)

## 🔬 백엔드 워크플로우 실시간 트레이스 (`/trace`)

사용자 입력이 LangGraph 노드를 거치며 **plain data(질의어·벡터DB·웹검색)가 어디서
참조되고, 어떤 데이터가 어떤 간선을 타고 이동하며, 각 단계에서 어떻게 정제되어 최종
답변이 되는지**를 실시간으로 보여주는 관측 화면입니다. 데모 영상에서 프론트엔드 화면과
백엔드 동작을 함께 드러내기 위한 수단입니다.

- **대시보드 URL**: `http://localhost:3000/trace` (세션 상세는 `http://localhost:3000/{sid}/trace`)
- **2D 데이터 흐름 그래프**: 노드를 레이어드 DAG로 2차원 배치하고 간선으로 연결합니다.
  - 실행된 경로의 간선은 초록색으로 흐르며, **어떤 데이터가 이동했는지**(`📦 사용자 요청`,
    `📦 country, purpose…`, `📦 search_results`)를 간선 위에 표시합니다.
  - 실행되지 않은 분기는 회색 처리되고, 간선에는 분기 조건(`RAG 결과 0건` 등)이 붙습니다.
  - **노드를 클릭하면** 설명·데이터 출처·정제 필드와 함께 **최근 실행 상세(실제 질의어·
    결과 수·출처 URL)**가 팝업으로 표시됩니다.
- **단계별 타임라인**: 각 노드가 참조한 입력과 산출을 표로 보여줍니다. 예) RAG 노드는 실제
  질의어·`country_code` 필터·결과 건수·매칭 비자를, Tavily 노드는 검색어·결과 수·출처
  URL·컨텍스트 길이를 명시 → "왜 폴백되었는지"가 한눈에 보입니다.
- **🔗 SPA 연동(실시간)**: 고객 SPA(`http://localhost:3000/`) 채팅창에 입력하면, 그 실행이
  대시보드(`http://localhost:3000/trace`)에 **실시간으로 함께 표시**됩니다. 화면(HTML)은
  Express(:3000)가 서빙하고 브라우저가 FastAPI(:8000)를 **CORS 로 직접 호출**합니다. 백엔드
  이벤트 버스가 `/chat/stream` 실행을 `/trace/live`(SSE) 구독자에게 브로드캐스트하며,
  EventSource(`/trace/live`)도 **cross-origin + CORS** 로 수신합니다. 대시보드를 별도 탭으로
  열어 두면 됩니다.

> 아래는 모두 **FastAPI(:8000)** 의 JSON/SSE 엔드포인트입니다. 대시보드 화면(`/trace`,
> `/{sid}/trace`)은 **Express(:3000)** 가 서빙하고, 이 화면들이 아래 엔드포인트를 CORS 로 호출합니다.

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/graph/topology` | 컴파일된 그래프 인트로스펙션(노드·엣지·간선 라벨) JSON |
| POST | `/chat/stream` | 노드 실행을 **SSE**로 스트리밍 + 이벤트 버스로 브로드캐스트 |
| GET | `/trace/live` | 이벤트 버스 구독 SSE — 외부(SPA) 실행을 실시간 수신 |
| POST | `/trace/run` | 대시보드 자체 입력 → 백그라운드 실행 후 브로드캐스트 |
| GET | `/trace/sessions` | 통합 허브용 세션 개요 JSON |

> ⚠️ 이벤트 버스는 **단일 uvicorn 워커**(인메모리 pub/sub) 기준입니다. 멀티 워커/수평
> 확장 시에는 Redis Pub/Sub 등 외부 브로커로 교체해야 합니다(prototype 한정).

### 확장 유연성 (노드/기능 추가 시 자동 반영)

트레이스는 `graph.astream(stream_mode="updates")` 와 `compiled.get_graph()`
인트로스펙션에 기반하므로 **노드를 추가/변경해도 트레이스 코드 수정이 필요 없습니다.**

1. `api/agent/graph.py` 에 노드를 추가한다. → 토폴로지·2D 그래프·스트림·대시보드에 자동 등장.
2. (선택) `api/agent/trace_meta.py` 에 한 줄씩 보강:
   - `NODE_META` — 노드 한글 라벨·아이콘·데이터 출처·정제 필드
   - `EDGE_LABELS` — 간선의 분기 조건 라벨
   - 생략해도 폴백이 동작한다.
3. (선택) 노드 안에서 `node_details` 에 진단 레코드를 append 하면 타임라인·팝업에 세부
   정보(질의어·결과 수 등)가 자동 표기된다. State 채널이라 누적·직렬화가 자동 처리된다.
4. URL 경로는 `api/routers/workflow.py` 상단 상수(`TOPOLOGY_PATH`/`STREAM_PATH`/
   `LIVE_PATH`/`RUN_PATH`/`DASHBOARD_PATH`)에서 한곳으로 관리하므로 경로 변경도 코드
   한 줄로 가능하다.

## 디렉토리 구조

```
visa_guide_ai/
├── docker-compose.yml       # web:3000 (SPA) / api:8000 (API) / vectordb:8002
├── Makefile                 # make up / make dev-api / make dev-web
├── .env.example             # API 키 템플릿
├── data/visas/{US,JP,GB,CA,AU,DE}/_all_visas.json
├── web/                     # 프론트엔드 정적 서버(Express, :3000)
│   ├── server.js            # HTML 서빙 + </head> 앞에 window.__API_BASE__ 주입
│   ├── package.json         # express 의존성 (start: node server.js)
│   ├── Dockerfile           # node:22-slim, npm ci
│   └── public/
│       ├── app.html         # 고객용 메인 SPA(API_BASE 로 /sessions·/chat/stream 직접 호출)
│       ├── trace.html       # 세션별 상세 트레이스(2D 그래프·vanilla JS)
│       └── trace_hub.html   # 통합 병렬 허브(세션별 간단 카드 + 상세 링크)
├── api/
│   ├── main.py              # FastAPI 앱 + 시작 시 자동 인제스트
│   ├── sessions_store.py    # 대화 세션 영속 스토어(파일 data/sessions.json)
│   ├── routers/
│   │   ├── chat.py          # POST /chat/  (+ 공유 build_initial_state)
│   │   ├── sessions.py      # 세션 CRUD·메타데이터·메시지 영속 RESTful
│   │   └── workflow.py      # 토폴로지·스트림·/trace/live·/trace/run·/trace/sessions (순수 JSON/SSE)
│   ├── knowledge/           # 도메인 지식(반입)
│   │   ├── exceptions.py    #   교차 예외규칙 21종(쉥겐·환승·ETA·I-539·신분변경·긴급발급…) → RAG 적재
│   │   └── search_hints.py  #   국가별 우선 공식도메인 + 검색어 템플릿
│   ├── agent/
│   │   ├── {state,graph,routing,config,domain}.py
│   │   ├── nodes/{intent,search,response,general,refine,learn,llm}.py  # learn=knowledge_writer
│   │   ├── event_bus.py     # SPA↔trace 브로드캐스트 pub/sub(+리플레이)
│   │   └── trace_meta.py    # 노드/간선 표시 메타데이터(확장 지점)
│   └── rag/{vectorstore,ingest}.py   # 비자 + 예외규칙 적재, search_exceptions, add_learned_visa
└── data/visas/...           # 국가별 비자 데이터(read-only 마운트)
```

---

## 실행 방법

### A. Docker Compose (권장)

```bash
cp .env.example .env      # SOLAR_API_KEY, TAVILY_API_KEY 입력
make up                   # 또는 docker compose up --build
# → 고객 UI: http://localhost:3000/ (Express SPA)
# → API:     http://localhost:8000  (FastAPI JSON/SSE)
```

### B. 로컬 실행 (Docker 없이)

이제 **두 프로세스**가 필요합니다(브라우저는 :3000 에 접속, web 은 node ≥18 필요).

```bash
cp .env.example .env      # API 키 입력
make setup                # 패키지 설치(api + web)
# 터미널 1
make dev-api              # FastAPI (:8000) — 순수 JSON/SSE API
# 터미널 2
make dev-web              # Express (:3000) — 고객 UI: http://localhost:3000/
```

로컬 실행 시 ChromaDB는 `chroma_data/` 폴더에 영속 저장됩니다(`PersistentClient`).

---

## API 엔드포인트

아래는 **FastAPI(:8000)** 의 JSON/SSE 엔드포인트입니다. 화면 HTML(`/`=고객 SPA,
`/trace`=통합 허브, `/{sid}/trace`=세션 상세)은 **Express(:3000)** 가 서빙하며, 브라우저가
아래 엔드포인트를 CORS 로 직접 호출합니다.

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/` | 서비스 정보 JSON(`{service, docs}`) |
| GET | `/health` | 헬스체크 |
| POST | `/chat/` | `{message, session_id, history}` → `{response, session_id}` |
| POST | `/chat/stream` | 동일 입력 → 노드 실행을 SSE로 스트리밍(+버스 브로드캐스트) |
| POST | `/chat/followups` | 대화 맥락 기반 **AI 후속 질문 칩** 4개 생성 |
| GET | `/graph/topology` | LangGraph 노드·엣지·간선 라벨 토폴로지 JSON |
| GET | `/trace/live?session_id=` | 브로드캐스트 SSE — `session_id` 주면 해당 세션만 |
| GET | `/trace/sessions` | 허브용 세션 개요 JSON |
| POST | `/trace/run` | 대시보드 자체 입력 → 백그라운드 실행·브로드캐스트 |
| GET·POST | `/sessions`, `/sessions/{sid}` | 대화 세션 CRUD(영속) |
| PATCH | `/sessions/{sid}` | 세션 메타데이터(이름·한줄설명·태그) 수정 |
| POST | `/sessions/{sid}/messages` | 메시지 추가(영속) |
| PUT | `/sessions/{sid}/last_run` | 최근 워크플로우 실행 저장 |
| POST | `/ingest` | 벡터 DB 강제 재적재 |

---

## 환경 변수 (`.env`)

```bash
LLM_PROVIDER=solar              # solar | openai
SOLAR_API_KEY=up_...
SOLAR_MODEL=solar-pro
OPENAI_API_KEY=sk-...           # LLM_PROVIDER=openai 시
TAVILY_API_KEY=tvly-...         # 없으면 RAG만으로 동작
```

**`API_BASE_URL`** (Express 프론트 서버용, 기본 `http://localhost:8000`): Express(`web/`)가
응답 HTML 의 `</head>` 앞에 `<script>window.__API_BASE__="…"</script>` 로 주입합니다. 각
화면은 이 값을 읽어 **FastAPI(:8000) 를 CORS 로 직접 호출**합니다(API/SSE 호출만 절대 URL,
페이지 네비게이션 링크는 Express 동일 출처라 상대경로 유지). ⚠️ 브라우저에 주입되는
주소이므로 Docker 에서도 컨테이너명(`api`)이 아니라 **호스트에서 접근 가능한
`http://localhost:8000`** 이어야 합니다. 트레이스 대시보드는 Express 의 `/{sid}/trace`(세션
상세)·`/trace`(통합 허브) 로 접근합니다.

---

## 추가 개선(2차)

- **의도 분류 강건화**: `intent_classifier`를 결정적(temperature=0)으로 실행하고
  `INTENT_MODEL`로 모델 교체 가능. 도메인 키워드(`VISA_KEYWORDS`)·국가/목적 신호가 있으면
  LLM 오판을 무시하고 비자 플로로 강제(예: "캐나다 취업"이 일반대화로 빠지는 문제 해결).
- **멀티 채팅 세션(ChatGPT/Claude 식)**: 사이드바에서 **➕ 새 대화** 생성·전환·삭제,
  대화별 맥락 유지(세션별 history). 첫 메시지로 대화 제목 자동 설정.
- **Tavily 검색어 정제**: 한국어 원문·`Korea` 관련 단어를 배제하고 `search_hints` 템플릿의
  **핵심 영어 쿼리(국가명 + visa + requirements/eligibility/official)**만 사용
  (예: `South Africa work visa eligibility requirements official`). 재생성 검색어도 동일 규칙.

## 추가 개선(3차)

- **데스크탑 트레이스 레이아웃**: `/trace`의 단계별 파이프라인을 데스크탑에서는 **전체 폭 반응형
  카드 그리드**(`repeat(auto-fill, minmax(330px,1fr))`)로 펼쳐 한눈에 비교합니다. 모바일(≤760px)
  에서는 단일 컬럼 세로 스크롤로 자동 전환(좁은 슬라이드/스크롤 강제 제거).
- **지식 자가 학습(knowledge_writer)**: 웹 검색 결과가 신뢰도 **good**(공식 도메인 포함·내용
  충분)이면 ChromaDB 비자 컬렉션에 **학습 문서로 upsert**(`origin=web_search`). 다음에 같은
  국가를 물으면 RAG로 즉시 답해 웹검색을 건너뜁니다(점진적 지식 축적). 이 저장 동작은 실시간
  트레이스에 `지식 학습 저장` 노드·간선으로 표시됩니다.
- **예외 시나리오 보강(13→21종)**: 시나리오 B(미국 관광 → 코로나로 귀국 불가 → **I-539** 체류
  연장·USCIS), 시나리오 C(일본 관광 → 현지 취업 제의 → **신분 변경 제한·출국 후 재신청·불법취업
  패널티**), **긴급/급행 비자(Expedite·Premium Processing)**, 오버스테이 입국금지(3/10년 바),
  유학생 근로시간, 여권 6개월 유효, 범죄경력(DUI) 입국거부, 디지털 노마드 비자 추가.
- **3-pane 프론트엔드**: 좌측 **다크(블랙) 사이드바**(대화 목록·예시·지원국가) · 중앙 **메인 대화**
  · 우측 **워크플로우 패널**(노드별 단계·소요시간·데이터 출처 카드). 첨부 레퍼런스 스타일에 맞춰
  색/디자인/UX를 보완(기존 기능 구조 유지).
- **워크플로우 패널 열기/닫기**: 헤더의 `🔬 워크플로우 열기/닫기` 토글로 우측 패널을 사이드바처럼
  접고 펼 수 있습니다(모바일·데스크탑 공통). 닫으면 대화가 전체 폭을 사용하고, 패널은 스크롤해도
  머무는 sticky 드로어로 동작합니다.
- **의도추출 키워드 폴백**: LLM이 `country`/`purpose`를 `null`로 반환(또는 파싱 실패)해도
  메시지에서 국가명(캐나다→CA…)·목적(취업→employment…)을 직접 보강해 워크플로 진입을
  **결정적**으로 만듭니다(`domain.detect_country/detect_purpose`). "캐나다 …취업"이 빈 추출로
  빠지는 문제 방지.
- **트레이스 그래프 가독성**: 실행 경로 노드와 화살표를 비활성(미실행) 노드 위에 그리도록
  z-index 레이어링 + 화살표 전용 오버레이 SVG(`#edgesFlow`)를 도입해, 선택된 노드/간선이
  다른 노드에 가려지지 않습니다.

## 추가 개선(4차) — 세션 영속·후속요청·세션별/통합 트레이스

- **선택 노드/간선 강조**: 실행 경로 노드는 **강한 글로우 + 다크 헤일로 그림자 + 약간 확대**로
  주변을 덮으며 **최상위 z-index**로 그려져 가시성을 극대화한다(hover 시 더 강조).
- **후속 요청 제안(ChatGPT 식)**: 답변 직후 `더 구체적으로 / 최신 정보로 확인 / 다른 비자 종류는? /
  공식 사이트 상세 탐색` 버튼을 노출. 클릭하면 **사용자가 입력한 것처럼 자동 실행**(멀티턴 맥락 활용).
- **공식 사이트 상세 탐색(딥서치)**: '상세 탐색/공식 사이트/최신 정보' 요청이면 RAG 를 건너뛰고
  곧장 `web_search_tool` 로 가서 **Tavily `search_depth=advanced` + 원문(raw_content)** 으로 깊게
  탐색한다(`intent → web_search_tool` 직행 엣지). 트레이스에 검색 깊이가 표시된다.
- **대화 영속화(새로고침 보존)**: 대화를 **백엔드 RESTful 세션 스토어**(`/sessions`, 파일
  `data/sessions.json`)로 이전. 활성 세션은 URL `?sid=` 로 유지되어 **새로고침/재시작에도 보존**된다.
- **세션 메타데이터**: 세션별 **이름 변경·한줄 설명·태그**(장기체류/취업/유학/여행…)를 사이드바에서
  편집·표시(태그 칩).
- **세션별 RESTful 트레이스(2a)**: 각 대화 세션은 `3000/?sid=<id>` ↔ `3000/{id}/trace` 로 1:1
  매핑된다. 이벤트마다 `session_id` 를 실어 `/trace/live?session_id=<id>` 로 **해당 세션만 필터**
  구독한다(병렬 실행 격리).
- **통합 병렬 허브(2b)**: `3000/trace` 는 모든 세션을 **간단한 동작(진행 바·현재 노드·상태)** 카드로
  한눈에 보여주고, 각 카드의 **상세 트레이스 ↗** 링크로 세션별 상세(`/{id}/trace`)로 이동한다.

## 추가 개선(5차) — AI 후속칩·반응형 트레이스 레이아웃·종합 검증

- **상황별 AI 후속 질문 칩**: 답변 직후 `POST /chat/followups` 로 대화 맥락(국가·목적·언급 비자)을
  반영한 후속 질문 4개를 **LLM 이 동적으로 생성**해 칩으로 노출(예: 캐나다 취업 → "Express Entry
  자격 요건은?", "Work Permit 처리 기간은?", "영주권 전환 절차는?"). + 고정 유틸 칩(공식 사이트
  상세 탐색). 칩은 세션 `last_run` 에 저장돼 새로고침에도 보존되며, 실패 시 정적 폴백.
- **트레이스 그래프 반응형 배치 + 사용자 줌**: 공간이 충분하면 **가로(행/LR)**, 좁으면
  **세로(열/TB)** 로 자동 배치(수동 ⇄ 토글로 자동/세로/가로 고정 가능). **줌(−/＋/맞춤/100%)** 으로
  2분할(프론트+트레이스 동시 관찰) 등 좁은 화면에서도 **모든 노드가 한눈에** 보이도록 사용자가
  크기를 조절. 타임라인·최종 답변은 그대로 유지.
- **종합 검증(시나리오 A/B/C + 전체 노드)**: 시나리오 A(캐나다 개발자 → Express Entry vs Work
  Permit 분기·요건/절차/기간), B(미국 I-539), C(일본 신분변경), 장기체류(독일 영주권), 교차규칙
  (쉥겐·환승), 긴급발급, 일반대화 오분류 방지, 신규 국가 웹검색→학습 저장→재사용, 딥서치를 모두
  검증. **9개 노드 전부 도달 가능**(query_refiner 는 웹검색 신뢰도 'poor' 시 동작 — 우선도메인
  검색이 안정적이라 평시 미발동, 라우팅/엣지로 도달성 확인).

## 데모 리뷰 반영(개선 이력)

- **장기 체류 비중 강화**: 단기→영주권·정착 경로와 갱신/전환 조건을 함께 안내(SYSTEM_PROMPT).
- **교차 예외규칙 보강**: 쉥겐↔비쉥겐, 환승, ESTA/eTA, 유효기간≠체류, 단·복수입국 등 13종 규칙을
  RAG에 적재하고 키워드+의미 하이브리드로 검색(`knowledge/exceptions.py`).
- **전세계 국가 대응**: 6개국은 RAG, 그 외는 `knowledge/search_hints.py`의 우선 공식도메인·검색어
  템플릿으로 Tavily 검색(예: 남아공→dha.gov.za, 프랑스→france-visas.gouv.fr).
- **검색 신뢰도 게이트 + 검색어 재생성 루프**: 공식 출처가 부족하면 LLM이 한국어→영어 검색어를
  재생성해 재검색(에이전트형 자기교정).
- **일반 대화 분기**: 비자 무관 질문이 비자 워크플로에 잘못 진입하지 않도록 `general_chat`로 분리.
- **멀티턴 맥락**: 직전 대화를 의도 추출에 반영(예: "캐나다 개발자 취업" 후 "그럼 영국은?" →
  영국·취업·개발자로 이어받음).
- **응답 토큰 스트리밍**: 최종 답변을 토큰 단위로 실시간 갱신(SPA·/trace 공통).
- **SPA ↔ /trace 실시간 연동**: 채팅 입력이 트레이스 대시보드에 실시간 브로드캐스트
  (이벤트 버스 + 캐시 무효화 + 직전 실행 리플레이).

## 제약 사항 (MVP)

- 정밀 RAG 데이터는 6개국(미국·일본·영국·캐나다·호주·독일), 그 외 국가는 웹검색 기반(정확도 변동)
- 실제 비자 신청 대행 / 승인 가능성 예측 없음
- 세션 영속 저장은 미지원(대화 history 기반 멀티턴만 지원)
- 한국어 전용 · 단일 프로세스(트레이스 브로드캐스트는 단일 uvicorn 워커 기준)

> ⚠️ 모든 비자 정보는 **참고용**이며, 실제 신청 시 해당 국가 공식 기관(대사관·이민국)에서 최신 정보를 반드시 확인하세요.
