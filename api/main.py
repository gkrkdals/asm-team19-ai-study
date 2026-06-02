from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import logging
import os

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting VisaGuide AI API...")
    try:
        from rag.ingest import ingest_all
        ingest_all()
    except Exception as e:
        logger.warning(f"Data ingestion skipped: {e}")
    yield
    logger.info("Shutting down...")


app = FastAPI(title="VisaGuide AI API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from routers.chat import router as chat_router
app.include_router(chat_router, prefix="/chat", tags=["chat"])

from routers.workflow import router as workflow_router
app.include_router(workflow_router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ingest")
def ingest():
    from rag.ingest import ingest_all
    total = ingest_all(force=True)
    return {"ingested": total}
