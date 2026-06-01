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

## 디렉토리 구조

```
visa_guide_ai/
├── docker-compose.yml       # api:8000 / ui:8501 / vectordb:8002
├── Makefile                 # make up / make dev-api / make dev-ui
├── .env.example             # API 키 템플릿
├── data/visas/{US,JP,GB,CA,AU,DE}/_all_visas.json
├── api/
│   ├── main.py              # FastAPI 앱 + 시작 시 자동 인제스트
│   ├── routers/chat.py      # POST /chat/
│   ├── agent/{state,nodes,graph}.py
│   └── rag/{vectorstore,ingest}.py
└── ui/app.py                # Streamlit 채팅 UI
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

---

## 제약 사항 (MVP)

- 6개국 한정 (미국·일본·영국·캐나다·호주·독일)
- 실제 비자 신청 대행 / 승인 가능성 예측 없음
- 세션 간 영속 대화 기록 미지원 (세션 내 State만 유지)
- 한국어 전용

> ⚠️ 모든 비자 정보는 **참고용**이며, 실제 신청 시 해당 국가 공식 기관(대사관·이민국)에서 최신 정보를 반드시 확인하세요.
