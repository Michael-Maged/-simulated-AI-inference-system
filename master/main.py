import os
import asyncio
import logging
import sys

import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException
from prometheus_client import make_asgi_app, Gauge, Counter

sys.path.insert(0, "/app")
from common.models import HeartbeatRequest, DispatchRequest, WorkerStatus
from master.worker_registry import WorkerRegistry
from master.circuit_breaker import CircuitBreaker
from master.queue_processor import process_request

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
WORKER_HOSTS = os.getenv("WORKER_HOSTS", "worker-1:9001")
HEARTBEAT_TIMEOUT = int(os.getenv("HEARTBEAT_TIMEOUT_SECONDS", "15"))
CB_THRESHOLD = int(os.getenv("CIRCUIT_BREAKER_THRESHOLD", "5"))
CB_COOLDOWN = int(os.getenv("CIRCUIT_BREAKER_COOLDOWN_SECONDS", "30"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

WORKERS_HEALTHY = Gauge("master_workers_healthy", "Number of healthy workers")
QUEUE_DEPTH = Gauge("master_queue_depth", "Request queue depth")
REQUESTS_FAILED = Counter("master_requests_failed_total", "Failed requests after all retries")

app = FastAPI(title="Master Coordinator")
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

_redis: aioredis.Redis | None = None
_registry: WorkerRegistry | None = None
_circuit_breakers: dict = {}


@app.on_event("startup")
async def startup():
    global _redis, _registry, _circuit_breakers
    _redis = aioredis.from_url(REDIS_URL)
    _registry = WorkerRegistry(_redis, timeout=HEARTBEAT_TIMEOUT)
    for entry in WORKER_HOSTS.split(","):
        host, port = entry.strip().split(":")
        worker_id = host
        _registry.register_worker(worker_id, host, int(port))
        _circuit_breakers[worker_id] = CircuitBreaker(worker_id, _redis, CB_THRESHOLD, CB_COOLDOWN)
    asyncio.create_task(_heartbeat_monitor())
    log.info(f"Master started with workers: {WORKER_HOSTS}")


async def _heartbeat_monitor():
    while True:
        await asyncio.sleep(5)
        await _registry.check_health()
        healthy = _registry.get_healthy_workers()
        WORKERS_HEALTHY.set(len(healthy))


@app.get("/health")
async def health():
    return {"status": "ok", "service": "master"}


@app.post("/heartbeat")
async def heartbeat(body: HeartbeatRequest):
    await _registry.heartbeat(body.worker_id, body.queue_depth, body.last_latency_ms)
    return {"status": "ok"}


@app.post("/dispatch")
async def dispatch(body: DispatchRequest):
    try:
        result = await process_request(
            _redis, _registry, _circuit_breakers,
            body.request_id, body.prompt, body.max_tokens, MAX_RETRIES,
        )
        return result
    except RuntimeError as e:
        REQUESTS_FAILED.inc()
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/workers", response_model=list[WorkerStatus])
async def list_workers():
    out = []
    for w in _registry.all_workers():
        cb = _circuit_breakers.get(w.worker_id)
        state = await cb.get_state() if cb else "unknown"
        out.append(WorkerStatus(
            worker_id=w.worker_id,
            alive=w.alive,
            circuit_state=state,
            queue_depth=w.queue_depth,
            last_latency_ms=w.last_latency_ms,
        ))
    return out
