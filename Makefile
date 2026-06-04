.PHONY: up down build logs ingest dev-api dev-web setup

# 고객 UI = http://localhost:3000/ (Express web), API = http://localhost:8000 (FastAPI)

# ── Docker Compose ────────────────────────────────────────────────────────
# up/up-d: web(:3000, SPA) + api(:8000, JSON/SSE API) + vectordb(:8002) 스택을 빌드·기동
up:
	docker compose up --build

up-d:
	docker compose up --build -d

# down: 스택 중지 + 볼륨 삭제(-v) → Chroma 데이터가 지워짐
down:
	docker compose down -v

logs:
	docker compose logs -f

# 벡터 DB 데이터 강제 재적재
ingest:
	curl -s -X POST http://localhost:8000/ingest | python3 -m json.tool

# ── 로컬 개발 (Docker 없이) ───────────────────────────────────────────────
setup:
	cp -n .env.example .env || true
	pip install -r api/requirements.txt
	cd web && npm install
	@echo "\n.env 파일에 API 키를 입력한 후 make dev-api(:8000) + make dev-web(:3000) 을 실행하세요. (고객 UI = http://localhost:3000/)"

dev-api:
	cd api && uvicorn main:app --reload --port 8000

# dev-web: Express 프론트 로컬 실행(:3000). API_BASE_URL 로 FastAPI(:8000) 직접 호출.
dev-web:
	cd web && npm install && API_BASE_URL=http://localhost:8000 PORT=3000 node server.js

# ── 헬스체크 ─────────────────────────────────────────────────────────────
health:
	curl -s http://localhost:8000/health | python3 -m json.tool
