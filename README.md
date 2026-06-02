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
intent_classifier ──┬─ (국가+목적 파악) ─→ visa_rag_search ─┬─ (결과 O) ─→ response_formatter ─→ END
                    │                                       └─ (결과 X) ─→ web_search_tool ─→ ┘
                    ├─ (예외 키워드 감지) ─→ exception_handler ──────────────────────────────→ ┘
                    └─ (정보 부족) ───────────────────────────────────────────→ response_formatter
```

- **intent_classifier**: 사용자 입력에서 국가·목적·기간·직업 추출 + 예외 키워드(연장/변경/거절) 감지
- **visa_rag_search**: ChromaDB 벡터 검색
- **web_search_tool**: RAG 미커버 시 Tavily 폴백
- **exception_handler**: 체류 연장·신분 변경·비자 거절 전용 처리
- **response_formatter**: 추천 비자/요건/서류/주의사항/공식 링크 구조화

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
│   ├── static/trace.html    # 실시간 트레이스 대시보드 (의존성 없는 vanilla JS)
│   ├── agent/
│   │   ├── {state,graph,routing,config,domain}.py
│   │   ├── nodes/{intent,search,response,llm}.py  # 노드가 node_details 진단 기록
│   │   ├── event_bus.py     # Streamlit↔trace 브로드캐스트 pub/sub
│   │   └── trace_meta.py    # 노드/간선 표시 메타데이터(확장 지점)
│   └── rag/{vectorstore,ingest}.py
└── ui/app.py                # Streamlit 채팅 UI (+ 인라인 워크플로우 스트리밍)
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

## 제약 사항 (MVP)

- 6개국 한정 (미국·일본·영국·캐나다·호주·독일)
- 실제 비자 신청 대행 / 승인 가능성 예측 없음
- 세션 간 영속 대화 기록 미지원 (세션 내 State만 유지)
- 한국어 전용

> ⚠️ 모든 비자 정보는 **참고용**이며, 실제 신청 시 해당 국가 공식 기관(대사관·이민국)에서 최신 정보를 반드시 확인하세요.
