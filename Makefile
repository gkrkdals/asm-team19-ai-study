.PHONY: up down build logs ingest dev-api setup

# 고객 UI = http://localhost:8000/ (FastAPI 가 서빙하는 SPA: api/static/app.html)

# ── Docker Compose ────────────────────────────────────────────────────────
# up/up-d: api(:8000, SPA 서빙) + vectordb(:8002) 스택을 빌드·기동
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
	@echo "\n.env 파일에 API 키를 입력한 후 make dev-api 를 실행하세요. (고객 UI = http://localhost:8000/)"

dev-api:
	cd api && uvicorn main:app --reload --port 8000

# ── 헬스체크 ─────────────────────────────────────────────────────────────
health:
	curl -s http://localhost:8000/health | python3 -m json.tool
