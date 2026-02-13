from collections import defaultdict, deque
from datetime import datetime, timezone
import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import api_router
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.services.seed import seed_demo_data


settings = get_settings()
app = FastAPI(title=settings.app_name, debug=settings.debug)
logger = logging.getLogger("navfund.api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_request_buckets: dict[str, deque[float]] = defaultdict(deque)


@app.middleware("http")
async def request_log_and_rate_limit(request: Request, call_next):
    started = time.monotonic()
    key = f"{request.client.host if request.client else 'unknown'}:{request.url.path}"
    now = time.time()
    bucket = _request_buckets[key]
    while bucket and now - bucket[0] > settings.rate_limit_window_seconds:
        bucket.popleft()
    if len(bucket) >= settings.rate_limit_requests:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Please retry later."},
        )
    bucket.append(now)

    try:
        response = await call_next(request)
    except Exception as exc:  # pragma: no cover
        logger.exception("Unhandled error for %s %s", request.method, request.url.path, exc_info=exc)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    elapsed_ms = (time.monotonic() - started) * 1000
    logger.info(
        "%s %s -> %s %.2fms",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "timestamp": datetime.now(timezone.utc).isoformat()}


app.include_router(api_router, prefix=settings.api_prefix)


@app.on_event("startup")
def startup_event() -> None:
    if settings.auto_create_schema:
        Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_demo_data(db)
