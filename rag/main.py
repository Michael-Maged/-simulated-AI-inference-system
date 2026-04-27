import os
import logging
import chromadb
from fastapi import FastAPI, Query
from prometheus_client import make_asgi_app, Histogram, Counter
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

CHROMADB_HOST = os.getenv("CHROMADB_HOST", "localhost")
CHROMADB_PORT = int(os.getenv("CHROMADB_PORT", "8000"))
EMBED_MODEL = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "corpus")

RETRIEVE_LATENCY = Histogram("rag_retrieve_latency_seconds", "Retrieval latency")
CHUNKS_RETURNED = Counter("rag_chunks_returned_total", "Total chunks returned")

app = FastAPI(title="RAG Retriever")
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

_model: SentenceTransformer | None = None
_collection = None


@app.on_event("startup")
async def startup():
    global _model, _collection
    log.info(f"Loading embedding model {EMBED_MODEL}...")
    _model = SentenceTransformer(EMBED_MODEL)
    client = chromadb.HttpClient(host=CHROMADB_HOST, port=CHROMADB_PORT)
    _collection = client.get_or_create_collection(COLLECTION_NAME)
    log.info(f"RAG retriever ready. Collection '{COLLECTION_NAME}' has {_collection.count()} chunks.")


@app.get("/health")
async def health():
    count = _collection.count() if _collection else 0
    return {"status": "ok", "service": "rag-retriever", "chunks_indexed": count}


@app.get("/retrieve")
async def retrieve(prompt: str = Query(...), top_k: int = Query(default=3, ge=1, le=10)):
    with RETRIEVE_LATENCY.time():
        embedding = _model.encode([prompt])[0].tolist()
        count = _collection.count()
        if count == 0:
            return {"chunks": [], "prompt": prompt}
        results = _collection.query(
            query_embeddings=[embedding],
            n_results=min(top_k, count),
            include=["documents", "metadatas", "distances"],
        )
        chunks = []
        if results["documents"]:
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                chunks.append({
                    "text": doc,
                    "source": meta.get("source", "unknown"),
                    "score": float(1.0 - dist),
                })
        CHUNKS_RETURNED.inc(len(chunks))
    return {"chunks": chunks, "prompt": prompt}
