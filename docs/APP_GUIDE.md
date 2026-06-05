# 🛂 VisaGuide AI — 앱 실행 및 사용 설명서

---

## 1. 아키텍처 구조

```
브라우저
  └── http://localhost:3000          ← Node.js (Express) 프론트엔드
          │  API 요청 (fetch/SSE)
          ▼
      http://localhost:8000          ← FastAPI 백엔드 (LangGraph + RAG)
          │
          ▼
      ChromaDB (로컬 파일 or Docker)  ← 비자 지식 벡터 DB
```

| 서비스 | 역할 | 포트 |
|--------|------|------|
| **web** (Node.js/Express) | HTML 정적 서빙, API_BASE 주입 | `3000` |
| **api** (FastAPI) | LangGraph 워크플로우, RAG, 세션 관리 | `8000` |
| **vectordb** (ChromaDB) | 비자 문서 벡터 저장소 | `8002` (Docker 시) |

---

## 2. 사전 준비

### 2-1. 환경변수 설정
```bash
cp .env.example .env
```

`.env` 파일에 아래 값 입력:
```env
ANTHROPIC_API_KEY=sk-ant-...     # Claude API 키
TAVILY_API_KEY=tvly-...          # Tavily 웹검색 키
```

### 2-2. 의존성 설치
```bash
# Python (백엔드)
pip install -r api/requirements.txt

# Node.js (프론트엔드)
cd web && npm install
```

---

## 3. 서버 실행 방법

### 방법 A — 로컬 직접 실행 (개발용, 권장)

**터미널 1: FastAPI 백엔드**
```bash
cd api
uvicorn main:app --reload --port 8000
```

**터미널 2: Node.js 프론트엔드**
```bash
cd web
API_BASE_URL=http://localhost:8000 PORT=3000 node server.js
```

또는 Makefile 단축 명령:
```bash
make dev-api   # 터미널 1: FastAPI (포트 8000)
make dev-web   # 터미널 2: Node.js (포트 3000)
```

### 방법 B — Docker Compose (운영/데모용)

```bash
# 빌드 + 전체 스택 시작
make up        # 포그라운드 (로그 출력)
make up-d      # 백그라운드 (데몬)

# 중지
make down
```

> ⚠️ `make down`은 ChromaDB 볼륨을 삭제합니다. 학습 데이터가 초기화됩니다.

---

## 4. 접속 주소

| 페이지 | 주소 | 설명 |
|--------|------|------|
| 🛂 **고객 UI** | http://localhost:3000/ | 비자 AI 챗봇 |
| 🔬 **워크플로우 트레이스** | http://localhost:3000/trace | 전체 세션 트레이스 허브 |
| 🔬 **세션별 트레이스** | http://localhost:3000/{sid}/trace | 특정 세션 실시간 워크플로우 |
| 📋 **API 문서** | http://localhost:8000/docs | FastAPI Swagger UI |
| 💚 **API 헬스체크** | http://localhost:8000/health | `{"status":"ok"}` |

---

## 5. 앱 사용법

### 5-1. 기본 질문

세 가지 정보를 포함해서 질문하면 최적의 답변을 받을 수 있습니다:

| 정보 | 예시 |
|------|------|
| 🌍 목적지 (나라) | 캐나다, 일본, 독일… |
| 🎯 목적 | 취업, 유학, 여행, 장기거주… |
| 📅 기간 | 1년, 6개월, 단기… |

**예시 질문:**
```
"캐나다에서 소프트웨어 개발자로 취업하고 싶어요"
"일본 유학 비자 6개월 받으려면 어떻게 해야 하나요?"
"독일 워킹홀리데이 조건 알려줘"
"미국 관광비자로 입국 후 체류 연장이 가능한가요?"
```

### 5-2. 워크플로우 트레이스 보기

질문 전송 후 우측 상단 **🔬 워크플로우** 버튼을 클릭하면 LangGraph가 어떤 노드를 거쳐 답변을 만들었는지 실시간으로 확인할 수 있습니다.

```
intent_classifier → visa_rag_search → (RAG 히트 시) response_formatter
                                    → (미스 시) web_search_tool → search_quality_gate
                                                                 → knowledge_writer (학습저장)
                                                                 → response_formatter
```

### 5-3. 지원 국가

기본 RAG 데이터: 🇺🇸 미국 · 🇯🇵 일본 · 🇬🇧 영국 · 🇨🇦 캐나다 · 🇦🇺 호주 · 🇩🇪 독일 (78개 비자)

그 외 국가: 자동으로 웹검색 후 ChromaDB에 학습 저장 → **이후 재질문 시 검색 없이 즉시 응답**

---

## 6. 서버 종료

```bash
# 로컬 실행 시
pkill -f "uvicorn"
pkill -f "node server.js"

# Docker 시
make down
```

---

## 7. 문제 해결

### 포트가 이미 사용 중
```bash
lsof -i :8000   # 또는 :3000
kill -9 <PID>
```

### ChromaDB 지식 강제 재적재
```bash
make ingest
# 또는
curl -X POST http://localhost:8000/ingest
```

### 로그 확인 (로컬 실행 시)
```bash
tail -f /tmp/fastapi.log   # FastAPI 로그
tail -f /tmp/web.log       # Node.js 로그
```

### Docker 로그 확인
```bash
make logs
docker compose logs -f api    # FastAPI만
docker compose logs -f web    # Node.js만
```

---

## 8. 디렉터리 구조

```
asm-team19-ai-study/
├── api/                    # FastAPI 백엔드
│   ├── main.py             # 앱 진입점
│   ├── agent/              # LangGraph 워크플로우
│   │   ├── nodes/          # 9개 노드 (intent, search, learn…)
│   │   ├── graph.py        # 그래프 빌드
│   │   └── routing.py      # 조건부 간선 로직
│   ├── rag/                # ChromaDB RAG
│   ├── routers/            # API 라우터 (chat, sessions, trace…)
│   └── static/             # 트레이스 HTML (trace.html 등)
├── web/                    # Node.js 프론트엔드
│   ├── server.js           # Express 서버 (API_BASE 주입)
│   └── public/             # 정적 HTML
│       ├── app.html        # 고객 챗봇 UI
│       ├── trace.html      # 세션별 트레이스
│       └── trace_hub.html  # 전체 트레이스 허브
├── data/                   # 비자 원본 데이터 (JSON)
├── tests/                  # 검증 시나리오 및 결과
├── docs/                   # 문서 모음
│   ├── VERSION.md          # 버전별 변경 이력
│   ├── CHROMADB_VALIDATION_REPORT.md
│   └── ROUND_9_VALIDATION_REPORT.md
├── docker-compose.yml
├── Makefile
└── README.md
```
