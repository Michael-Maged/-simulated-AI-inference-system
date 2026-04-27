import os
import uuid
import json
import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_client import make_asgi_app, Counter, Gauge

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
INGEST_QUEUE = os.getenv("INGEST_QUEUE", "queue:ingest")

JOBS_SUBMITTED = Counter("ingestion_jobs_total", "Total ingestion jobs submitted")
QUEUE_DEPTH = Gauge("ingestion_queue_depth", "Current ingestion queue depth")

app = FastAPI(title="Ingestion Service")
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

_redis: aioredis.Redis | None = None


class IngestRequest(BaseModel):
    filename: str
    text: str


@app.on_event("startup")
async def startup():
    global _redis
    _redis = aioredis.from_url(REDIS_URL)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ingestion-service"}


@app.post("/ingest")
async def ingest(body: IngestRequest):
    job_id = str(uuid.uuid4())
    payload = json.dumps({"job_id": job_id, "filename": body.filename, "text": body.text})
    await _redis.lpush(INGEST_QUEUE, payload)
    await _redis.hset(f"job:{job_id}", mapping={"status": "pending", "filename": body.filename})
    JOBS_SUBMITTED.inc()
    depth = await _redis.llen(INGEST_QUEUE)
    QUEUE_DEPTH.set(depth)
    return {"job_id": job_id, "status": "pending"}


@app.get("/ingest/{job_id}/status")
async def job_status(job_id: str):
    data = await _redis.hgetall(f"job:{job_id}")
    if not data:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, **{k.decode(): v.decode() for k, v in data.items()}}
