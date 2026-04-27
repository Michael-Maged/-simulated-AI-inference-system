import os
from fastapi import FastAPI
from prometheus_client import make_asgi_app

app = FastAPI(title="Load Balancer")
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "load-balancer"}


@app.post("/infer")
async def infer(body: dict):
    return {"status": "stub — not yet implemented"}


@app.get("/admin/strategy")
async def get_strategy():
    return {"strategy": os.getenv("LB_STRATEGY", "round_robin")}
