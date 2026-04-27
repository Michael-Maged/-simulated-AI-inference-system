import uuid
from fastapi import FastAPI
from pydantic import BaseModel
from prometheus_client import make_asgi_app

app = FastAPI(title="Ingestion Service")
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


class IngestRequest(BaseModel):
    filename: str
    text: str


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ingestion-service"}


@app.post("/ingest")
async def ingest(body: IngestRequest):
    return {"job_id": str(uuid.uuid4()), "status": "stub"}


@app.get("/ingest/{job_id}/status")
async def job_status(job_id: str):
    return {"job_id": job_id, "status": "stub"}
