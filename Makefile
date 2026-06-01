.PHONY: up down build logs ingest dev-api dev-ui setup

# ── Docker Compose ────────────────────────────────────────────────────────
up:
	docker compose up --build

up-d:
	docker compose up --build -d

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
	pip install -r ui/requirements.txt
	@echo "\n.env 파일에 API 키를 입력한 후 make dev-api / make dev-ui 를 실행하세요."

dev-api:
	cd api && uvicorn main:app --reload --port 8000

dev-ui:
	cd ui && streamlit run app.py --server.port 8501

# ── 헬스체크 ─────────────────────────────────────────────────────────────
health:
	curl -s http://localhost:8000/health | python3 -m json.tool
