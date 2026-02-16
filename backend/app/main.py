from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
import time

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import api_router
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.services.seed import seed_demo_data


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

settings = get_settings()
logger = logging.getLogger("navfund.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── startup ──
    if settings.auto_create_schema:
        Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        try:
            seed_demo_data(db)
        except Exception:
            db.rollback()
            logger.exception("Skipping demo seed due to startup error.")
    logger.info("NAVCore API ready.")
    yield
    # ── shutdown ──
    engine.dispose()
    logger.info("NAVCore API shutdown complete.")


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    lifespan=lifespan,
)

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


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "status": "ok",
        "health": "/healthz",
        "api_root": f"{settings.api_prefix}/health",
        "docs": "/docs",
    }


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)


app.include_router(api_router, prefix=settings.api_prefix)
