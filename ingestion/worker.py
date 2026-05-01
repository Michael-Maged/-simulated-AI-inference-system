import os
import json
import logging
import uuid
import redis
import chromadb
from sentence_transformers import SentenceTransformer
from chunker import chunk_text

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
INGEST_QUEUE = os.getenv("INGEST_QUEUE", "queue:ingest")
CHROMADB_HOST = os.getenv("CHROMADB_HOST", "localhost")
CHROMADB_PORT = int(os.getenv("CHROMADB_PORT", "8000"))
EMBED_MODEL = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "corpus")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "512"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "64"))


def run():
    log.info("Ingestion worker starting...")
    r = redis.from_url(REDIS_URL)
    chroma = chromadb.HttpClient(host=CHROMADB_HOST, port=CHROMADB_PORT)
    collection = chroma.get_or_create_collection(COLLECTION_NAME)
    model = SentenceTransformer(EMBED_MODEL)
    log.info("Ingestion worker ready. Waiting for jobs...")

    while True:
        result = r.brpop(INGEST_QUEUE, timeout=5)
        if result is None:
            continue
        _, raw = result
        job_id = None
        try:
            job = json.loads(raw)
            job_id = job["job_id"]
            filename = job["filename"]
            text = job["text"]

            r.hset(f"job:{job_id}", "status", "processing")
            log.info(f"Processing job {job_id}: {filename}")

            chunks = chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)
            log.info(f"Split into {len(chunks)} chunks")

            embeddings = model.encode(chunks).tolist()
            ids = [f"{filename}-{i}-{uuid.uuid4().hex[:8]}" for i in range(len(chunks))]
            metadatas = [{"source": filename, "chunk_index": i} for i in range(len(chunks))]

            collection.upsert(ids=ids, embeddings=embeddings, documents=chunks, metadatas=metadatas)
            r.hset(f"job:{job_id}", "status", "done")
            log.info(f"Job {job_id} done: {len(chunks)} chunks ingested from {filename}")

        except Exception as e:
            log.error(f"Job failed: {e}")
            if job_id:
                try:
                    r.hset(f"job:{job_id}", "status", "failed")
                except Exception:
                    pass


if __name__ == "__main__":
    run()
