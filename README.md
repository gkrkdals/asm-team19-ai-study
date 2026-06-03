# 🛂 VisaGuide AI

목적·기간·상황에 따라 최적의 해외 비자를 AI가 탐색·추천해 주는 **Agentic 정보 서비스** (프로토타입).

> "어느 나라에서, 얼마나, 무슨 목적으로?" — 세 가지 입력만으로 필요한 비자 정보를 즉시 안내하는 한국어 AI 챗봇

지원 국가: 🇺🇸 미국 · 🇯🇵 일본 · 🇬🇧 영국 · 🇨🇦 캐나다 · 🇦🇺 호주 · 🇩🇪 독일 (총 78개 비자 데이터)

---

## 기술 스택

| 레이어 | 기술 |
|---|---|
| Frontend | Streamlit (채팅 UI) |
| Backend API | FastAPI (REST 엔드포인트) |
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
                   │                                                            (신뢰도 충분) ─────────┴→ response_formatter
                   └─ (정보 부족) ─────────────────────────────────────────────────────→ response_formatter (재질문)
```

- **intent_classifier**: 국가(ISO 코드)·목적·기간·직업 추출 + **비자 관련 여부 판별** + 예외 키워드(연장/변경/거절·**쉥겐/환승/ESTA** 등) 감지 + **멀티턴 맥락 이어받기**(이전 대화 반영)
- **general_chat**: 비자와 무관한 질문을 간단히 응대하고 도메인으로 유도 (노드 오진입 방지)
- **visa_rag_search**: ChromaDB 비자 문서 검색 + **교차 예외규칙(extra_context)** 병합
- **web_search_tool**: 6개국 외 국가까지 대응. `search_hints`의 **우선 공식도메인(include_domains)**·검색어 템플릿 적용
- **search_quality_gate**: 웹 결과 신뢰도(공식 출처 포함·내용량) 평가
- **query_refiner**: 신뢰도가 낮으면 **LLM이 한국어→영어 공식 검색어를 재생성**해 재검색(최대 2회 루프)
- **exception_handler**: 연장·변경·거절 + 쉥겐·환승·전자여행허가 등 **교차 규칙**을 키워드+의미 하이브리드로 검색
- **response_formatter**: 추천 비자/요건/서류/주의사항/공식 링크 구조화 (**토큰 스트리밍**)

## 🔬 백엔드 워크플로우 실시간 트레이스 (`/trace`)

사용자 입력이 LangGraph 노드를 거치며 **plain data(질의어·벡터DB·웹검색)가 어디서
참조되고, 어떤 데이터가 어떤 간선을 타고 이동하며, 각 단계에서 어떻게 정제되어 최종
답변이 되는지**를 실시간으로 보여주는 관측 화면입니다. 데모 영상에서 프론트엔드 화면과
백엔드 동작을 함께 드러내기 위한 수단입니다.

- **대시보드 URL**: `http://localhost:8000/trace`
- **2D 데이터 흐름 그래프**: 노드를 레이어드 DAG로 2차원 배치하고 간선으로 연결합니다.
  - 실행된 경로의 간선은 초록색으로 흐르며, **어떤 데이터가 이동했는지**(`📦 사용자 요청`,
    `📦 country, purpose…`, `📦 search_results`)를 간선 위에 표시합니다.
  - 실행되지 않은 분기는 회색 처리되고, 간선에는 분기 조건(`RAG 결과 0건` 등)이 붙습니다.
  - **노드를 클릭하면** 설명·데이터 출처·정제 필드와 함께 **최근 실행 상세(실제 질의어·
    결과 수·출처 URL)**가 팝업으로 표시됩니다.
- **단계별 타임라인**: 각 노드가 참조한 입력과 산출을 표로 보여줍니다. 예) RAG 노드는 실제
  질의어·`country_code` 필터·결과 건수·매칭 비자를, Tavily 노드는 검색어·결과 수·출처
  URL·컨텍스트 길이를 명시 → "왜 폴백되었는지"가 한눈에 보입니다.
- **🔗 Streamlit 연동(실시간)**: `http://localhost:8501` 채팅창에 입력하면, 그 실행이
  대시보드(`/trace`)에 **실시간으로 함께 표시**됩니다. 백엔드 이벤트 버스가 `/chat/stream`
  실행을 `/trace/live`(SSE) 구독자에게 브로드캐스트하는 구조입니다. 사이드바
  **"워크플로우 실시간 보기 ↗"** 버튼으로 대시보드를 열어 두면 됩니다.

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/graph/topology` | 컴파일된 그래프 인트로스펙션(노드·엣지·간선 라벨) JSON |
| POST | `/chat/stream` | 노드 실행을 **SSE**로 스트리밍 + 이벤트 버스로 브로드캐스트 |
| GET | `/trace/live` | 이벤트 버스 구독 SSE — 외부(Streamlit) 실행을 실시간 수신 |
| POST | `/trace/run` | 대시보드 자체 입력 → 백그라운드 실행 후 브로드캐스트 |
| GET | `/trace` | 위 엔드포인트들을 소비하는 라이브 대시보드 HTML |

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
├── docker-compose.yml       # api:8000 / ui:8501 / vectordb:8002
├── Makefile                 # make up / make dev-api / make dev-ui
├── .env.example             # API 키 템플릿
├── data/visas/{US,JP,GB,CA,AU,DE}/_all_visas.json
├── api/
│   ├── main.py              # FastAPI 앱 + 시작 시 자동 인제스트
│   ├── routers/
│   │   ├── chat.py          # POST /chat/  (+ 공유 build_initial_state)
│   │   └── workflow.py      # GET /graph/topology · POST /chat/stream · GET /trace
│   ├── static/trace.html    # 실시간 트레이스 대시보드 (2D 그래프·vanilla JS)
│   ├── knowledge/           # 도메인 지식(반입)
│   │   ├── exceptions.py    #   교차 예외규칙 13종(쉥겐·환승·ETA…) → RAG 적재
│   │   └── search_hints.py  #   국가별 우선 공식도메인 + 검색어 템플릿
│   ├── agent/
│   │   ├── {state,graph,routing,config,domain}.py
│   │   ├── nodes/{intent,search,response,general,refine,llm}.py
│   │   ├── event_bus.py     # Streamlit↔trace 브로드캐스트 pub/sub(+리플레이)
│   │   └── trace_meta.py    # 노드/간선 표시 메타데이터(확장 지점)
│   └── rag/{vectorstore,ingest}.py   # 비자 + 예외규칙 적재, search_exceptions
└── ui/app.py                # Streamlit 채팅 UI(+워크플로우 단계·토큰 스트리밍)
```

---

## 실행 방법

### A. Docker Compose (권장)

```bash
cp .env.example .env      # SOLAR_API_KEY, TAVILY_API_KEY 입력
make up                   # 또는 docker compose up --build
# → http://localhost:8501
```

### B. 로컬 실행 (Docker 없이)

```bash
cp .env.example .env      # API 키 입력
make setup                # 패키지 설치
make dev-api              # 터미널 1: FastAPI (8000)
make dev-ui               # 터미널 2: Streamlit (8501)
```

로컬 실행 시 ChromaDB는 `chroma_data/` 폴더에 영속 저장됩니다(`PersistentClient`).

---

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/health` | 헬스체크 |
| POST | `/chat/` | `{message, session_id, history}` → `{response, session_id}` |
| POST | `/chat/stream` | 동일 입력 → 노드 실행을 SSE로 스트리밍(+버스 브로드캐스트) |
| GET | `/graph/topology` | LangGraph 노드·엣지·간선 라벨 토폴로지 JSON |
| GET | `/trace` | 워크플로우 실시간 트레이스 대시보드 |
| GET | `/trace/live` | 외부(Streamlit) 실행을 수신하는 브로드캐스트 SSE |
| POST | `/trace/run` | 대시보드 자체 입력 → 백그라운드 실행·브로드캐스트 |
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

UI 전용(선택) 환경 변수:

```bash
API_BASE_URL=http://localhost:8000        # Streamlit → API 서버 주소
TRACE_URL=http://localhost:8000/trace     # 사이드바 '워크플로우 실시간 보기' 링크 대상
```

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
- **응답 토큰 스트리밍**: 최종 답변을 토큰 단위로 실시간 갱신(Streamlit·/trace 공통).
- **Streamlit ↔ /trace 실시간 연동**: 채팅 입력이 트레이스 대시보드에 실시간 브로드캐스트
  (이벤트 버스 + 캐시 무효화 + 직전 실행 리플레이).

## 제약 사항 (MVP)

- 정밀 RAG 데이터는 6개국(미국·일본·영국·캐나다·호주·독일), 그 외 국가는 웹검색 기반(정확도 변동)
- 실제 비자 신청 대행 / 승인 가능성 예측 없음
- 세션 영속 저장은 미지원(대화 history 기반 멀티턴만 지원)
- 한국어 전용 · 단일 프로세스(트레이스 브로드캐스트는 단일 uvicorn 워커 기준)

> ⚠️ 모든 비자 정보는 **참고용**이며, 실제 신청 시 해당 국가 공식 기관(대사관·이민국)에서 최신 정보를 반드시 확인하세요.
