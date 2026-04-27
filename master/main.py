from fastapi import FastAPI
from prometheus_client import make_asgi_app

app = FastAPI(title="Master Coordinator")
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "master"}


@app.post("/dispatch")
async def dispatch(body: dict):
    return {"status": "stub"}


@app.post("/heartbeat")
async def heartbeat(body: dict):
    return {"status": "stub"}


@app.get("/workers")
async def list_workers():
    return {"workers": []}
