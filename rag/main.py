from fastapi import FastAPI
from prometheus_client import make_asgi_app

app = FastAPI(title="RAG Retriever")
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "rag-retriever"}


@app.get("/retrieve")
async def retrieve(prompt: str, top_k: int = 3):
    return {"chunks": [], "prompt": prompt}
