import os
import time

INGESTION_URL = os.getenv("INGESTION_URL", "http://localhost:8003")

if __name__ == "__main__":
    print("Bootstrap: stub complete", flush=True)
