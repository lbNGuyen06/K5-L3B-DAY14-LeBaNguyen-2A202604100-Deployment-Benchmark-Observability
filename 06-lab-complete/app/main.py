"""
Production AI Agent — Part 6 Final Project
"""
import time
import json
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field

from app.config import settings
from app.redis_client import redis_healthy
from app.auth import verify_api_key
from app.rate_limiter import check_rate_limit
from app.cost_guard import check_budget, record_cost
from utils.mock_llm import ask as llm_ask


# ============================================================
# TIÊU CHÍ 10: Structured JSON Logging
# ============================================================
class JsonFormatter(logging.Formatter):
    """Mọi dòng log của app đều là 1 JSON object hợp lệ."""
    def format(self, record):
        log_entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "lvl": record.levelname,
            "name": record.name,
            "msg": record.getMessage(),
        }
        return json.dumps(log_entry)


# Cấu hình logger xuất ra console dạng JSON
log_handler = logging.StreamHandler()
log_handler.setFormatter(JsonFormatter())
logger = logging.getLogger("agent")
logger.setLevel(logging.INFO)
logger.handlers = [log_handler]
logger.propagate = False


# ============================================================
# TIÊU CHÍ 11: Lifespan & Graceful Shutdown
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application starting up...")
    yield
    logger.info("Application shutting down gracefully...")


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


# ============================================================
# TIÊU CHÍ 4: GET /health — Liveness probe (luôn 200)
# ============================================================
@app.get("/health")
def health():
    return {"status": "ok", "environment": settings.environment}


# ============================================================
# TIÊU CHÍ 5: GET /ready — Readiness probe (503 khi mất Redis)
# ============================================================
@app.get("/ready")
def ready():
    if not redis_healthy():
        logger.warning("Readiness probe failed: Redis not connected")
        raise HTTPException(status_code=503, detail="Redis service unavailable")
    return {"status": "ready"}


@app.post("/ask")
def ask(body: AskRequest, key: str = Depends(verify_api_key)):
    check_rate_limit(key)
    check_budget()
    logger.info(f"Processing question: {body.question[:50]}")
    answer = llm_ask(body.question)
    
    # Tính toán tokens và cộng dồn chi phí
    in_tokens = len(body.question.split()) * 2
    out_tokens = len(answer.split()) * 2
    record_cost(in_tokens, out_tokens)

    return {"question": body.question, "answer": answer}

