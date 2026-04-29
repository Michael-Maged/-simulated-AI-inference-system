# Distributed AI Inference System
**CSE354 — Distributed Computing | Ain Shams University | 2025/2026**

---

## Quick Start (come back here every time)

```
Step 1 → Open Docker Desktop, wait until it says "Engine running"
Step 2 → docker compose up --build
Step 3 → Wait for: "Model ready. Starting gRPC server..." (5-15 min first time)
Step 4 → Test it works (see Testing section below)
Step 5 → Open Grafana: http://localhost:3000  (admin / admin)
```

**To stop everything:**
```
docker compose down
```

**To start again (faster, no rebuild):**
```
docker compose up
```

---

## Testing the System (PowerShell)

```powershell
# Send one AI question
Invoke-WebRequest -Uri http://localhost:8000/infer `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"prompt": "What is a circuit breaker?", "max_tokens": 100}' `
  | Select-Object -ExpandProperty Content

# Send it again — second time should say "cached": true and be much faster
Invoke-WebRequest -Uri http://localhost:8000/infer `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"prompt": "What is a circuit breaker?", "max_tokens": 100}' `
  | Select-Object -ExpandProperty Content

# Check all worker statuses
Invoke-WebRequest -Uri http://localhost:8001/workers | Select-Object -ExpandProperty Content
```

---

## Run the Load Test (1000 users)

```powershell
pip install locust
locust -f client/locustfile.py --host=http://localhost:8000 --users 1000 --spawn-rate 50 --run-time 10m --headless --csv=docs/results/peak_1000
```

While it runs, open Grafana to watch live metrics.

---

## Chaos Test (break things on purpose)

```powershell
# Kill a worker while load test is running
python client/chaos.py --kill worker-2

# See what happened to workers
python client/chaos.py --status

# Bring it back
python client/chaos.py --recover worker-2
```

---

## Generate Report Graphs

```powershell
pip install matplotlib pandas
python client/plot_results.py --csv-prefix docs/results/peak_1000 --out docs/results/
```

Graphs saved to `docs/results/` — use them in the report.

---

## Run Unit Tests

```powershell
pip install pytest pytest-asyncio redis numpy
pytest tests/ -v
```

Should show: `27 passed`

---

## What Is This Project?

### The Problem
If 1000 people ask an AI a question at the same time, one computer can't handle it. Each AI response takes 2-8 seconds. Person #1000 would wait over an hour.

### The Solution
Spread the work across many services that cooperate — a **distributed system**.

### The Restaurant Analogy

| Restaurant | Our System |
|---|---|
| Front door / host | **Load Balancer** — receives all requests |
| Head waiter | **Master** — manages who does what |
| Chefs in the kitchen | **Workers** — run the actual AI |
| Recipe book | **RAG** — looks up relevant facts before answering |
| Librarian | **Ingestion Pipeline** — reads documents and stores them |
| Security cameras | **Prometheus + Grafana** — watches everything |

---

## The 3 Special Features (Extras for High Grade)

### 1. Semantic Cache (inside Load Balancer)
If user A asks "What is a circuit breaker?" and user B asks "Explain circuit breakers please", these are the same question worded differently. The cache detects this using AI math (cosine similarity of text embeddings) and returns the stored answer instantly (~10ms) instead of running the AI again (2-8 seconds).

### 2. Adaptive Load-Aware Routing (inside Load Balancer)
Instead of just counting requests per worker, we track how fast each worker actually responds (rolling p95 latency). We always route to the fastest worker. If worker-3 is slow today, it automatically gets fewer requests.

### 3. Circuit Breakers (inside Master)
If a worker keeps failing, we "trip" its circuit (like a fuse). All requests to it fail instantly instead of waiting. After 30 seconds we test it. If it recovered → normal again. If not → stay tripped.

```
CLOSED (normal) ──5 failures──► OPEN (fail fast)
                                      │
                                 30 seconds
                                      ▼
                               HALF-OPEN (testing)
                                  │         │
                              success     failure
                                  │         │
                               CLOSED    OPEN again
```

---

## How a Request Travels Through the System

```
User asks: "What is a circuit breaker?"
         │
         ▼
Load Balancer :8000
  ├─ Converts question to 384 numbers (embedding)
  ├─ Checks Redis cache — similar question answered before?
  │   YES → return cached answer instantly (~10ms)
  │   NO  → continue...
  ├─ Picks fastest worker using Load-Aware strategy
  └─ Forwards to Master
         │
         ▼
Master :8001
  ├─ Checks worker circuit breaker — is it CLOSED?
  ├─ Dispatches via gRPC to e.g. worker-2
         │
         ▼
Worker-2 :9002
  ├─ Asks RAG retriever: "find context about circuit breakers"
  │      ▼
  │   RAG Retriever :8002
  │     ├─ Converts question to 384 numbers
  │     ├─ Searches ChromaDB for 3 most relevant text chunks
  │     └─ Returns: "A circuit breaker is a design pattern..."
  │
  ├─ Builds augmented prompt:
  │     [CONTEXT] retrieved text [QUESTION] user question
  ├─ Sends to Ollama (local AI model phi3:mini)
  └─ Returns AI answer
         │
         ▼
Master → Load Balancer
  └─ Stores answer in Redis cache for next time
         │
         ▼
User gets answer in ~3-8 seconds (or ~10ms if cached)
```

---

## File-by-File Explanation

### `docker-compose.yml`
The master blueprint. Describes all 16 containers. Running `docker compose up` reads this file and starts everything. You never need to start services manually.

### `common/models.py`
Defines the shape of data passed between services. Like a contract — everyone agrees what a "request" and "response" look like.

### `common/protos/worker.proto`
Defines the gRPC "phone protocol" between the master and workers. gRPC is 5-10x faster than HTTP for internal calls. Used by Google, Netflix, Uber in production.

### `load_balancer/strategies.py`
Three routing algorithms:
- **Round Robin** — takes turns (worker 1, 2, 3, 1, 2, 3...)
- **Least Connections** — picks whoever has fewest active requests
- **Load-Aware** — picks whoever has been responding fastest recently

Change with env var `LB_STRATEGY=round_robin|least_connections|load_aware`

### `load_balancer/cache.py`
The semantic cache. Converts questions to number vectors, finds similar cached questions, returns stored answers instantly.

### `load_balancer/main.py`
The full load balancer FastAPI app. Receives requests, checks cache, routes to master.

### `master/worker_registry.py`
Tracks which workers are alive. Workers send heartbeats every 5 seconds. No heartbeat for 15 seconds → worker marked DEAD.

### `master/circuit_breaker.py`
The safety fuse. Three states: CLOSED (normal), OPEN (failing, reject fast), HALF-OPEN (testing recovery).

### `master/queue_processor.py`
Picks a healthy worker and dispatches the request via gRPC. Retries on a different worker if one fails (up to 3 attempts). Never silently drops requests.

### `master/main.py`
Full master coordinator. Handles `/dispatch`, `/heartbeat`, `/workers` endpoints. Background task monitors worker health every 5 seconds.

### `workers/entrypoint.sh`
Startup script inside each worker container:
1. Start Ollama
2. Wait until Ollama is ready
3. Download phi3:mini (first time only, ~2GB)
4. Start gRPC server

### `workers/inference.py`
The AI logic. Gets context from RAG, builds augmented prompt, calls Ollama, returns response with timing.

### `workers/server.py`
gRPC server. Handles inference requests, sends heartbeats to master, exposes Prometheus metrics on port 8080.

### `rag/main.py`
The RAG retriever. Converts a question to a number vector, searches ChromaDB for the 3 most relevant text chunks, returns them as context.

### `ingestion/chunker.py`
Splits long documents into overlapping 512-word chunks. Overlap ensures concepts that span chunk boundaries are not lost.

### `ingestion/worker.py`
Reads documents from the Redis queue, splits into chunks, converts to number vectors (embeddings), stores in ChromaDB.

### `ingestion/bootstrap.py`
Runs once at startup. Feeds all documents in `corpus/` through the ingestion pipeline so ChromaDB has knowledge to search.

### `corpus/distributed_systems.txt` + `corpus/ai_inference.txt`
The knowledge base. Text about distributed systems and AI inference. Workers use this to give better answers via RAG.

### `monitoring/prometheus.yml`
Tells Prometheus to scrape metrics from all services every 15 seconds.

### `monitoring/alerts.yml`
Alert rules: no workers for 30s = critical, queue > 500 for 60s = warning, p95 latency > 10s = warning.

### `monitoring/grafana/provisioning/`
Auto-configures Grafana on startup. No manual setup needed. Dashboard has 7 panels: throughput, latency percentiles, worker health, cache hit rate, queue depth, worker latency, failures.

### `client/locustfile.py`
Load test. Simulates NormalUsers (short questions, 0.1-1s pause) and HeavyUsers (long questions, no pause). Run with 100/500/1000/1500 users to measure performance.

### `client/chaos.py`
Chaos testing. Kill/slow/recover workers during a live load test to prove fault tolerance.

### `client/plot_results.py`
Generates matplotlib graphs from Locust CSV data for the report: throughput curve, latency percentiles, strategy comparison bar chart, scaling curve.

### `tests/`
27 unit tests. Run without Docker. Test routing strategies, semantic cache, circuit breaker state machine, worker registry, and text chunker.

---

## Services and Ports

| Service | Port | What it does |
|---|---|---|
| load-balancer | **8000** | Public API — send requests here |
| master | 8001 | Coordinator — manages workers |
| rag-retriever | 8002 | Retrieves context from ChromaDB |
| ingestion-service | 8003 | Accepts new documents |
| chromadb | 8004 | Vector database |
| worker-1 | 9001 | AI worker (gRPC) |
| worker-2 | 9002 | AI worker (gRPC) |
| worker-3 | 9003 | AI worker (gRPC) |
| worker-4 | 9004 | AI worker (gRPC) |
| redis | 6379 | Queue, cache, heartbeat state |
| prometheus | 9090 | Metrics collector |
| **grafana** | **3000** | **Live dashboard** |

---

## Tech Stack

| Tool | Why |
|---|---|
| Python 3.11 | Required by spec |
| FastAPI | Async web framework, fast, auto-docs |
| gRPC | 5-10x faster than HTTP for internal calls |
| Ollama + phi3:mini | Local AI model, no internet needed, free |
| ChromaDB | Vector database for AI similarity search |
| sentence-transformers | Converts text to number vectors |
| Redis | In-memory store: queues, cache, counters |
| Prometheus | Collects metrics from all services |
| Grafana | Displays metrics as live graphs |
| Locust | Simulates 1000+ concurrent users |
| Docker Compose | One command starts everything |

---

## Common Problems

**Build fails: "zstd not found"**
Already fixed in Dockerfile. Just run `docker compose up --build` again.

**Workers take too long to start**
Normal on first run. phi3:mini is ~2GB and downloads once. Subsequent starts are fast (model is cached in a Docker volume).

**`curl` doesn't work in PowerShell**
Use `Invoke-WebRequest` instead (see Testing section above). Or type `curl.exe` with `.exe` to use real curl if installed.

**A worker shows "circuit OPEN" in status**
The worker had 5 consecutive failures. Wait 30 seconds — it will auto-transition to HALF-OPEN and test itself. Or restart it: `docker compose restart worker-2`

**Grafana shows no data**
Wait 30-60 seconds after startup. Prometheus needs time to scrape the first metrics.
