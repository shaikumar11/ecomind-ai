"""
app.py — FastAPI backend for EcoMind AI.

Run with:
    uvicorn app:app --reload

Then open http://127.0.0.1:8000/docs for interactive API docs, or point
the ecomind_ai.html frontend at this server — it detects the backend
automatically on load and falls back to its built-in offline engine if
this server isn't reachable (see README.md).
"""

import time
import traceback

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

from config import settings
from logging_config import logger
from rag import EcoMindRAG, KnowledgeBaseError, estimate_footprint, CATEGORY_LABELS

app = FastAPI(
    title="EcoMind AI",
    description="Retrieval-augmented sustainability assistant — 1M1B AI for "
                 "Sustainability Virtual Internship (IBM SkillsBuild & AICTE).",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    rag = EcoMindRAG()
except KnowledgeBaseError as exc:
    # Fail loudly and immediately rather than serving a broken /chat
    # endpoint that 500s on every request.
    logger.critical("Failed to start EcoMind AI: %s", exc)
    raise


# ---------------------------------------------------------------- middleware

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.error(
            "%s %s -> UNHANDLED EXCEPTION (%.1fms)\n%s",
            request.method, request.url.path, duration_ms, traceback.format_exc(),
        )
        raise
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s -> %d (%.1fms)",
        request.method, request.url.path, response.status_code, duration_ms,
    )
    return response


# ------------------------------------------------------------- error handlers

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"error": str(exc)})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled error on %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error. Check server logs for details."},
    )


# ---------------------------------------------------------------- schemas

class ChatRequest(BaseModel):
    query: str

    @field_validator("query")
    @classmethod
    def query_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("query must not be empty")
        if len(v) > settings.max_query_len:
            raise ValueError(f"query must be at most {settings.max_query_len} characters")
        return v.strip()


class FootprintRequest(BaseModel):
    car_km_week: float = 0
    elec_kwh_month: float = 0
    diet: str = "average"       # meat | average | veg | vegan
    short_flights: int = 0
    long_flights: int = 0

    @field_validator("car_km_week", "elec_kwh_month")
    @classmethod
    def non_negative_float(cls, v: float) -> float:
        if v < 0:
            raise ValueError("value must be >= 0")
        return v

    @field_validator("short_flights", "long_flights")
    @classmethod
    def non_negative_int(cls, v: int) -> int:
        if v < 0:
            raise ValueError("value must be >= 0")
        return v

    @field_validator("diet")
    @classmethod
    def diet_allowed(cls, v: str) -> str:
        if v not in settings.allowed_diets:
            raise ValueError(f"diet must be one of {list(settings.allowed_diets)}")
        return v


# ---------------------------------------------------------------- routes

@app.get("/")
def root():
    return {
        "app": "EcoMind AI",
        "version": app.version,
        "endpoints": ["/health", "/topics", "/chat", "/footprint"],
    }


@app.get("/health")
def health():
    return {"status": "ok", "kb_entries": len(rag.kb)}


@app.get("/topics")
def topics():
    return {"topics": CATEGORY_LABELS}


@app.post("/chat")
def chat(req: ChatRequest):
    return rag.answer(req.query)


@app.post("/footprint")
def footprint(req: FootprintRequest):
    return estimate_footprint(
        rag,
        car_km_week=req.car_km_week,
        elec_kwh_month=req.elec_kwh_month,
        diet=req.diet,
        short_flights=req.short_flights,
        long_flights=req.long_flights,
    )
