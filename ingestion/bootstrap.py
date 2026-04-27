import os
import time
import pathlib
import httpx

INGESTION_URL = os.getenv("INGESTION_URL", "http://localhost:8003")
CORPUS_DIR = pathlib.Path(__file__).parent.parent / "corpus"


def wait_for_service():
    print("Bootstrap: waiting for ingestion service...", flush=True)
    for _ in range(30):
        try:
            r = httpx.get(f"{INGESTION_URL}/health", timeout=3.0)
            if r.status_code == 200:
                print("Ingestion service ready.", flush=True)
                return
        except Exception:
            pass
        time.sleep(2)
    raise RuntimeError("Ingestion service did not become ready in time")


def ingest_corpus():
    txt_files = list(CORPUS_DIR.glob("*.txt"))
    if not txt_files:
        print(f"No .txt files found in {CORPUS_DIR}", flush=True)
        return
    for path in txt_files:
        text = path.read_text(encoding="utf-8")
        print(f"Ingesting {path.name} ({len(text)} chars)...", flush=True)
        resp = httpx.post(
            f"{INGESTION_URL}/ingest",
            json={"filename": path.name, "text": text},
            timeout=10.0,
        )
        resp.raise_for_status()
        print(f"  → job_id={resp.json()['job_id']}", flush=True)
    print("Bootstrap complete.", flush=True)


if __name__ == "__main__":
    wait_for_service()
    time.sleep(3)
    ingest_corpus()
