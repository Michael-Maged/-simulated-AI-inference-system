import os
import uuid
import time
import logging
import asyncio

import httpx
import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, Request
from prometheus_client import make_asgi_app, Counter, Histogram

import sys
sys.path.insert(0, "/app")
from common.models import InferRequest, InferResponse
from strategies import RoundRobinStrategy, LeastConnectionsStrategy, LoadAwareStrategy
from cache import SemanticCache

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
MASTER_URL = os.getenv("MASTER_URL", "http://localhost:8001")
LB_STRATEGY = os.getenv("LB_STRATEGY", "round_robin")
_cache_enabled = os.getenv("CACHE_ENABLED", "false").lower() == "true"
CACHE_THRESHOLD = float(os.getenv("CACHE_SIMILARITY_THRESHOLD", "0.88"))
CACHE_TTL = int(os.getenv("CACHE_TTL_SECONDS", "3600"))
EMBED_MODEL = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

REQUESTS_TOTAL = Counter("lb_requests_total", "Total requests", ["strategy", "cached"])
CACHE_HITS = Counter("lb_cache_hits_total", "Cache hits")
CACHE_MISSES = Counter("lb_cache_misses_total", "Cache misses")
LATENCY = Histogram("lb_response_latency_seconds", "End-to-end latency",
                    buckets=[0.01, 0.1, 0.5, 1, 2, 5, 10, 30])

app = FastAPI(title="Load Balancer")
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

_redis: aioredis.Redis | None = None
_cache: SemanticCache | None = None
_strategy = None


@app.on_event("startup")
async def startup():
    global _redis, _cache, _strategy
    _redis = aioredis.from_url(REDIS_URL)
    _cache = SemanticCache(REDIS_URL, CACHE_THRESHOLD, CACHE_TTL, EMBED_MODEL)
    if LB_STRATEGY == "round_robin":
        _strategy = RoundRobinStrategy()
    elif LB_STRATEGY == "least_connections":
        _strategy = LeastConnectionsStrategy()
    else:
        _strategy = LoadAwareStrategy()
    log.info(f"Load balancer started with strategy={LB_STRATEGY}")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "load-balancer", "strategy": LB_STRATEGY}


@app.post("/infer", response_model=InferResponse)
async def infer(request: Request, body: InferRequest):
    start = time.time()
    request_id = str(uuid.uuid4())

    if _cache_enabled:
        cached_response = await _cache.get(body.prompt)
        if cached_response:
            CACHE_HITS.inc()
            REQUESTS_TOTAL.labels(strategy=LB_STRATEGY, cached="true").inc()
            LATENCY.observe(time.time() - start)
            return InferResponse(
                request_id=request_id,
                response=cached_response,
                latency_ms=(time.time() - start) * 1000,
                cached=True,
            )

    CACHE_MISSES.inc()
    REQUESTS_TOTAL.labels(strategy=LB_STRATEGY, cached="false").inc()

    async def _dispatch():
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(
                f"{MASTER_URL}/dispatch",
                json={
                    "request_id": request_id,
                    "prompt": body.prompt,
                    "max_tokens": body.max_tokens,
                    "priority": body.priority,
                },
            )
            resp.raise_for_status()
            return resp.json()

    dispatch_task = asyncio.create_task(_dispatch())

    # Poll for client disconnect every second — cancel work if client left
    while not dispatch_task.done():
        if await request.is_disconnected():
            dispatch_task.cancel()
            log.info(f"Client disconnected, cancelled request {request_id}")
            raise HTTPException(status_code=499, detail="Client disconnected")
        await asyncio.sleep(1)

    try:
        data = dispatch_task.result()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Master error: {e}")
    except asyncio.CancelledError:
        raise HTTPException(status_code=499, detail="Client disconnected")

    latency = (time.time() - start) * 1000
    LATENCY.observe(latency / 1000)

    if _cache_enabled:
        await _cache.set(body.prompt, data["response"])

    return InferResponse(
        request_id=request_id,
        response=data["response"],
        latency_ms=latency,
        cached=False,
        worker_id=data.get("worker_id", ""),
    )


@app.delete("/admin/cache")
async def clear_cache():
    keys = await _redis.keys("cache:embed:*")
    if keys:
        await _redis.delete(*keys)
    return {"deleted": len(keys)}


@app.put("/admin/cache/toggle")
async def toggle_cache(enabled: bool):
    global _cache_enabled
    _cache_enabled = enabled
    log.info(f"Cache {'enabled' if enabled else 'disabled'} at runtime")
    return {"cache_enabled": _cache_enabled}


@app.get("/admin/cache/status")
async def cache_status():
    keys = await _redis.keys("cache:embed:*")
    return {"cache_enabled": _cache_enabled, "entries": len(keys)}


@app.get("/admin/strategy")
async def get_strategy():
    return {"strategy": LB_STRATEGY}


@app.put("/admin/strategy")
async def set_strategy(strategy: str):
    global LB_STRATEGY, _strategy
    if strategy not in ("round_robin", "least_connections", "load_aware"):
        raise HTTPException(status_code=400, detail="Invalid strategy")
    LB_STRATEGY = strategy
    if strategy == "round_robin":
        _strategy = RoundRobinStrategy()
    elif strategy == "least_connections":
        _strategy = LeastConnectionsStrategy()
    else:
        _strategy = LoadAwareStrategy()
    return {"strategy": LB_STRATEGY}
