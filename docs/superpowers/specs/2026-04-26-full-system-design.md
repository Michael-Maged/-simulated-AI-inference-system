# Full System Design — Distributed AI Inference System
**Date:** 2026-04-26  
**Course:** CSE354 — Distributed Computing, Ain Shams University  
**Target grade band:** 89%+

---

## How to Read This Document

This document explains **what we are building, why each piece exists, and how everything connects**. It is written so that someone with no prior knowledge of distributed systems can understand it. Every section has:
- A plain-English explanation of what the component does
- Why we chose this approach
- How it connects to the rest of the system

---

## 1. The Big Picture — What Are We Building?

### The Problem

Imagine you run a website where thousands of users can ask questions to an AI. Each question needs to be answered by a large language model (LLM) — a program that reads your question and generates a text response. The problem is:

- Each LLM response takes **2–10 seconds** to generate
- You have **1000+ users asking questions at the same time**
- If one machine crashes, **no user should lose their request**
- Some questions have been asked before — **why re-compute the same answer?**

This is the problem we are solving.

### Our Solution — A Distributed System

Instead of one powerful computer doing all the work, we spread the work across **many smaller services** that cooperate over a network. Think of it like a restaurant:

- The **load balancer** is the front door — it receives all customers (requests) and decides which table (worker) they go to
- The **master/coordinator** is the head waiter — it tracks which workers are busy, which have crashed, and manages the queue
- The **workers** are the chefs — they do the actual AI computation
- The **RAG service** is the reference library — before answering, workers look up relevant facts to include in their answer
- The **ingestion pipeline** is the librarian — it reads documents and stores them so the RAG service can find them

---

## 2. Technology Choices — Why These Tools?

| Tool | What It Does | Why We Chose It |
|---|---|---|
| **Python 3.11** | Programming language | Required by spec; huge ecosystem for AI |
| **FastAPI** | Web framework for our HTTP services | Async (handles many requests at once), automatic documentation, fast |
| **gRPC** | Communication between master and workers | Faster than HTTP for internal calls, strongly typed, used in production systems like Google and Netflix |
| **Ollama + phi3:mini** | Runs the actual AI model locally | Free, runs on CPU, no internet required |
| **ChromaDB** | Stores and searches document embeddings (vector database) | Easy to run in Docker, purpose-built for AI retrieval |
| **sentence-transformers** | Converts text to numbers (embeddings) for similarity search | Industry standard, small and fast |
| **Redis** | In-memory data store for queues, counters, cache | Extremely fast, supports pub/sub, sorted sets, lists — perfect for our use case |
| **Prometheus** | Collects metrics from all services | Industry standard, used everywhere in production |
| **Grafana** | Displays metrics as graphs | Works natively with Prometheus, beautiful dashboards |
| **Locust** | Simulates 1000+ users sending requests | Real load testing tool, has a web UI showing live results |
| **Docker Compose** | Starts all 13 services with one command | Reproducible, portable, industry standard for development |

---

## 3. Architecture — How All Services Connect

```
┌─────────────────────────────────────────────────────┐
│                   CLIENTS (Locust)                   │
│          1000+ simulated users sending requests      │
└─────────────────────┬───────────────────────────────┘
                      │ HTTP POST /infer
                      ▼
┌─────────────────────────────────────────────────────┐
│              LOAD BALANCER (port 8000)               │
│  • Receives ALL incoming requests                    │
│  • Checks semantic cache first (is this prompt       │
│    similar to one we already answered?)              │
│  • Chooses a routing strategy:                       │
│    - Round Robin: take turns                         │
│    - Least Connections: pick least busy worker       │
│    - Load-Aware: pick worker with best latency       │
│  • Forwards to Master                                │
└─────────────────────┬───────────────────────────────┘
                      │ HTTP POST /dispatch
                      ▼
┌─────────────────────────────────────────────────────┐
│            MASTER / COORDINATOR (port 8001)          │
│  • Maintains a list of all workers and their health  │
│  • Each worker sends a heartbeat every 5 seconds     │
│  • If a worker stops heartbeating → marked DEAD      │
│  • Has a circuit breaker per worker (explained below)│
│  • Puts requests in a Redis queue                    │
│  • Picks a healthy worker and sends via gRPC         │
│  • If worker fails → retries on another worker       │
└──────┬──────────────┬──────────────┬────────────────┘
       │              │              │
       │ gRPC         │ gRPC         │ gRPC
       ▼              ▼              ▼
┌──────────┐   ┌──────────┐   ┌──────────┐
│ WORKER 1 │   │ WORKER 2 │   │ WORKER 3 │  ... (up to 4)
│          │   │          │   │          │
│ • Runs   │   │ • Runs   │   │ • Runs   │
│   Ollama │   │   Ollama │   │   Ollama │
│ • Calls  │   │ • Calls  │   │ • Calls  │
│   RAG    │   │   RAG    │   │   RAG    │
└──────────┘   └──────────┘   └──────────┘
       │              │              │
       └──────────────┴──────────────┘
                      │ HTTP GET /retrieve
                      ▼
┌─────────────────────────────────────────────────────┐
│            RAG RETRIEVER (port 8002)                 │
│  • Worker sends the user's question here             │
│  • RAG converts question to a number vector          │
│  • Searches ChromaDB for the 3 most similar chunks   │
│  • Returns those chunks to the worker                │
│  • Worker adds them as context before asking Ollama  │
└─────────────────────┬───────────────────────────────┘
                      │ queries
                      ▼
┌─────────────────────────────────────────────────────┐
│                  CHROMADB (port 8004)                │
│  • Stores document chunks as number vectors          │
│  • Supports fast similarity search                   │
│  • Data stored on a Docker volume (persists restarts)│
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│          INGESTION SERVICE (port 8003)               │
│  • Accepts raw documents via HTTP                    │
│  • Pushes them to a Redis queue                      │
└─────────────────────┬───────────────────────────────┘
                      │ Redis queue
                      ▼
┌─────────────────────────────────────────────────────┐
│       INGESTION WORKERS (2 instances)                │
│  • Pop documents from Redis queue                    │
│  • Split into 512-token chunks with 64-token overlap │
│  • Embed each chunk with sentence-transformers       │
│  • Write to ChromaDB                                 │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│         MONITORING: PROMETHEUS + GRAFANA             │
│  • Prometheus scrapes /metrics from every service   │
│  • Grafana shows live graphs of everything          │
└─────────────────────────────────────────────────────┘
```

---

## 4. The Three Originality Features (Extras)

These three features go beyond a basic implementation and demonstrate real distributed systems engineering.

### 4.1 Circuit Breakers (inside Master)

**Plain English:** A circuit breaker is like a fuse in your home's electrical system. If too much current flows (too many failures), the fuse blows and cuts the circuit to prevent damage. When the problem is fixed, you reset the fuse and power comes back.

In our system, each worker has its own circuit breaker with three states:

```
         5 failures in a row           30s cooldown expires
CLOSED ──────────────────────► OPEN ──────────────────────► HALF-OPEN
  ▲                                                              │
  │                     probe request succeeds                  │
  └──────────────────────────────────────────────────────────────┘
                        probe request fails → back to OPEN
```

- **CLOSED** = normal operation, requests go through
- **OPEN** = worker is struggling, all requests to it are rejected instantly (fast-fail), they get rerouted to healthy workers. This prevents a slow/broken worker from blocking everything.
- **HALF-OPEN** = after 30 seconds, we try ONE request to see if the worker recovered. Success → back to CLOSED. Failure → back to OPEN for another 30 seconds.

**Why this matters:** Without circuit breakers, a slow worker makes every request that hits it wait 10+ seconds before timing out. With circuit breakers, requests fail fast (< 1ms) and get rerouted immediately.

**Reference:** Martin Fowler's Circuit Breaker pattern (https://martinfowler.com/bliki/CircuitBreaker.html)

### 4.2 Adaptive Load-Aware Routing (inside Load Balancer)

**Plain English:** Instead of just counting how many requests each worker has (least-connections), we track how fast each worker actually responds. A worker might have fewer requests but be very slow — we'd rather send to a slightly busier worker that answers quickly.

We maintain a **rolling p95 latency** for each worker over the last 5 minutes. "p95" means "95% of requests complete faster than this time." This is the standard metric used in production systems.

The routing algorithm:
1. Get the p95 latency score for each healthy worker (from Redis sorted set)
2. Pick the worker with the lowest p95 latency
3. If no latency data yet (brand new worker), fall back to least-connections

**Why this matters:** In a real heterogeneous cluster, some machines are faster than others. Load-aware routing automatically discovers and prefers faster workers without any manual configuration.

**Reference:** Google SRE Book, Chapter 20 — Load Balancing in the Datacenter

### 4.3 Semantic Caching (inside Load Balancer)

**Plain English:** If someone asks "What is the capital of France?" and 10 seconds later someone asks "Tell me the capital city of France", these are clearly the same question worded differently. We don't need to run the LLM twice.

Semantic caching works by:
1. Converting the incoming prompt into a number vector (embedding) using the same model as RAG
2. Searching Redis for a stored embedding that is "close enough" (cosine similarity > 0.88)
3. If found: return the cached answer instantly (< 10ms vs 2-10 seconds for real inference)
4. If not found: run inference normally, then store the answer + embedding in Redis with a 1-hour expiry

**Why this matters:** Under load, many users ask similar questions. Caching can reduce LLM calls by 30-60%, dramatically improving throughput and latency for cache hits.

**Reference:** Semantic caching is used in production at companies like Cohere and mentioned in the vLLM serving optimization literature.

---

## 5. Service Specifications

### 5.1 Load Balancer (`load_balancer/`)

**Port:** 8000  
**Technology:** FastAPI (async)

**Endpoints:**
```
POST /infer           — main inference endpoint (public-facing)
GET  /health          — liveness check
GET  /metrics         — Prometheus metrics
GET  /admin/strategy  — get current routing strategy
PUT  /admin/strategy  — change routing strategy at runtime
```

**Environment variables:**
```
LB_STRATEGY=round_robin|least_connections|load_aware
MASTER_URL=http://master:8001
REDIS_URL=redis://redis:6379
CACHE_SIMILARITY_THRESHOLD=0.88
CACHE_TTL_SECONDS=3600
EMBED_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

**Request flow:**
1. Receive `POST /infer` with `{ "prompt": "...", "max_tokens": 512, "priority": "normal" }`
2. Generate embedding for the prompt
3. Check Redis semantic cache
4. On cache miss: apply routing strategy → forward to `POST master:8001/dispatch`
5. Return response to client

### 5.2 Master / Coordinator (`master/`)

**Port:** 8001  
**Technology:** FastAPI (async) + background tasks

**Endpoints:**
```
POST /dispatch        — receive request from load balancer, queue it
POST /heartbeat       — workers call this every 5s
GET  /workers         — list all workers and their states
GET  /health
GET  /metrics
```

**Environment variables:**
```
REDIS_URL=redis://redis:6379
WORKER_HOSTS=worker-1:9001,worker-2:9002,worker-3:9003,worker-4:9004
HEARTBEAT_TIMEOUT_SECONDS=15
CIRCUIT_BREAKER_THRESHOLD=5
CIRCUIT_BREAKER_COOLDOWN_SECONDS=30
MAX_RETRIES=3
```

**Background tasks (run continuously):**
- `heartbeat_monitor`: checks last heartbeat timestamp every 5s, marks workers DEAD if stale
- `queue_processor`: pops from Redis queue, picks worker, dispatches via gRPC

### 5.3 Workers (`workers/`)

**Ports:** 9001–9004 (gRPC)  
**Technology:** gRPC server + Ollama (internal HTTP)

**gRPC service definition** (`common/protos/worker.proto`):
```protobuf
syntax = "proto3";
package worker;

service Worker {
  rpc Infer (InferRequest) returns (InferResponse);
  rpc Health (HealthRequest) returns (HealthResponse);
}

message InferRequest {
  string request_id = 1;
  string prompt     = 2;
  int32  max_tokens = 3;
  string priority   = 4;
}

message InferResponse {
  string request_id  = 1;
  string response    = 2;
  float  latency_ms  = 3;
  bool   rag_used    = 4;
}

message HealthRequest {}
message HealthResponse { bool ready = 1; }
```

**Environment variables:**
```
WORKER_ID=worker-1
GRPC_PORT=9001
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=phi3:mini
RAG_URL=http://rag-retriever:8002
MASTER_URL=http://master:8001
RAG_TOP_K=3
```

**Startup sequence:**
1. Start Ollama server in background (`ollama serve`)
2. Pull model (`ollama pull phi3:mini`) — skipped if already cached
3. Wait for Ollama `/api/tags` to respond (health gate, max 120s)
4. Start gRPC server
5. Begin sending heartbeats to master every 5s

### 5.4 RAG Retriever (`rag/`)

**Port:** 8002  
**Technology:** FastAPI (async)

**Endpoints:**
```
GET /retrieve?prompt={text}&top_k={n}   — returns top-k chunks
GET /health
GET /metrics
```

**Environment variables:**
```
CHROMADB_HOST=chromadb
CHROMADB_PORT=8004
EMBED_MODEL=sentence-transformers/all-MiniLM-L6-v2
COLLECTION_NAME=corpus
```

**Startup:** loads embedding model into memory once. All requests reuse the in-memory model.

### 5.5 Ingestion Service (`ingestion/`)

**Port:** 8003  
**Technology:** FastAPI (async)

**Endpoints:**
```
POST /ingest                    — submit a document
GET  /ingest/{job_id}/status    — check job status
GET  /health
GET  /metrics
```

**Environment variables:**
```
REDIS_URL=redis://redis:6379
INGEST_QUEUE=queue:ingest
```

### 5.6 Ingestion Workers (`ingestion/worker.py`, 2 instances)

**No HTTP port** — these are pure queue consumers.

**Algorithm:**
1. `BLPOP queue:ingest` — blocks waiting for work (Redis)
2. Split text into chunks: 512 tokens, 64-token overlap (sliding window)
3. For each chunk: embed with `all-MiniLM-L6-v2`
4. Upsert into ChromaDB collection with metadata
5. Mark job as `done` in Redis hash

**Environment variables:**
```
REDIS_URL=redis://redis:6379
CHROMADB_HOST=chromadb
CHROMADB_PORT=8004
EMBED_MODEL=sentence-transformers/all-MiniLM-L6-v2
COLLECTION_NAME=corpus
CHUNK_SIZE=512
CHUNK_OVERLAP=64
```

---

## 6. Data Flows

### 6.1 Normal Inference Request (cache miss)

```
1. Locust sends: POST load-balancer:8000/infer { prompt: "What is X?" }
2. Load balancer embeds prompt → checks Redis cache → MISS
3. Load balancer applies load-aware routing → selects worker-2
4. Load balancer forwards to: POST master:8001/dispatch { prompt, worker_hint: "worker-2" }
5. Master checks worker-2 circuit → CLOSED → pushes to Redis queue
6. Queue processor pops request → gRPC call to worker-2:9002
7. Worker-2 calls: GET rag:8002/retrieve?prompt=... → gets 3 chunks
8. Worker-2 builds augmented prompt: [CONTEXT]{chunks}[QUESTION]{prompt}
9. Worker-2 calls: POST ollama:11434/api/generate → gets response
10. Worker-2 returns InferResponse to master via gRPC
11. Master returns response to load balancer via HTTP
12. Load balancer stores response+embedding in Redis cache
13. Load balancer returns response to Locust client
```

### 6.2 Normal Inference Request (cache hit)

```
1. Locust sends: POST load-balancer:8000/infer { prompt: "Tell me what X is" }
2. Load balancer embeds prompt → checks Redis cache → HIT (similarity 0.94 > 0.88)
3. Load balancer returns cached response immediately
   Total time: ~10ms instead of 2000–8000ms
```

### 6.3 Worker Failure + Recovery

```
1. Worker-3 crashes (Docker container stops)
2. Master detects missing heartbeat after 15 seconds
3. Master marks worker-3 as DEAD
4. Any in-flight request to worker-3 → master retries on worker-1
5. Circuit breaker for worker-3 → OPEN
6. Grafana shows worker-3 as dead (circuit_state gauge = 0)
7. Worker-3 container restarts (Docker restart policy: always)
8. Worker-3 sends heartbeat → master marks ALIVE
9. Circuit breaker → HALF-OPEN → sends probe request
10. Probe succeeds → circuit → CLOSED
11. Worker-3 receives normal traffic again
```

### 6.4 Document Ingestion

```
1. Bootstrap script sends: POST ingestion:8003/ingest { filename: "doc1.txt", text: "..." }
2. Ingestion service pushes job to Redis queue:ingest
3. Ingestion worker-1 pops job
4. Splits into chunks, embeds each, writes to ChromaDB
5. Job marked done
6. Future RAG queries can now find content from doc1.txt
```

---

## 7. Monitoring — What We Measure and Why

Every service exposes a `/metrics` endpoint in Prometheus format. Prometheus scrapes all of them every 15 seconds. Grafana reads from Prometheus and displays live dashboards.

### Key Metrics

| Metric | What it means | Why it matters |
|---|---|---|
| `lb_requests_total` | Total requests received by load balancer | Shows overall system load |
| `lb_cache_hits_total` | Requests answered from cache | Proves semantic caching is working |
| `lb_response_latency_seconds` | How long each request took end-to-end | The most important user-facing metric |
| `master_workers_healthy` | How many workers are currently healthy | Shows system availability |
| `master_circuit_state` | Circuit breaker state per worker (0=open, 1=closed) | Shows fault tolerance in action |
| `master_queue_depth` | How many requests are waiting to be processed | Shows if we're keeping up with load |
| `worker_infer_latency_seconds` | Time for each worker to complete inference | Identifies slow workers |
| `worker_ollama_errors_total` | Errors from Ollama | Shows model health |
| `rag_retrieve_latency_seconds` | Time to retrieve RAG context | Shows if ChromaDB is a bottleneck |
| `ingestion_queue_depth` | Documents waiting to be ingested | Shows ingestion pipeline health |

### Grafana Dashboard Panels

1. **Request Throughput** — requests/second over time
2. **Latency Percentiles** — p50/p95/p99 as time series
3. **Worker Utilization** — % time each worker is processing requests
4. **Circuit Breaker States** — colour-coded: green=closed, red=open, yellow=half-open
5. **Cache Hit Rate** — hits/(hits+misses) as a percentage
6. **Queue Depth** — request backlog over time
7. **Ingestion Pipeline** — docs ingested over time

---

## 8. Load Testing Plan

We use **Locust** to simulate real user load. Locust runs as a Docker container and hits our load balancer.

### Test Scenarios

| Scenario | Concurrent Users | Duration | Purpose |
|---|---|---|---|
| Baseline | 100 | 10 min | Establish normal performance |
| Medium load | 500 | 10 min | Show system handling normal load |
| Peak load | 1000 | 10 min | Demonstrate the core requirement |
| Stress test | 1500 | 10 min | Find breaking point |

### Load Balancer Strategy Comparison

Run all three scenarios at 1000 users with each strategy:
1. Round Robin
2. Least Connections
3. Load-Aware

Generate a bar chart comparing p95 latency across strategies.

### Chaos Testing

While Locust runs at 1000 users:
1. Kill worker-2: `python client/chaos.py --kill worker-2`
2. Watch Grafana — queue depth spike, then recovery
3. Record recovery time (time from kill to all metrics back to normal)
4. Restart: `python client/chaos.py --recover worker-2`

---

## 9. Repository Structure

```
.
├── CLAUDE.md
├── docker-compose.yml
├── common/
│   ├── protos/
│   │   └── worker.proto          ← gRPC service definition
│   └── models.py                 ← shared Pydantic models
├── load_balancer/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                   ← FastAPI app + routing strategies
│   ├── cache.py                  ← semantic cache logic
│   └── strategies.py             ← round_robin, least_conn, load_aware
├── master/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                   ← FastAPI app + /dispatch + /heartbeat
│   ├── circuit_breaker.py        ← circuit breaker state machine
│   ├── worker_registry.py        ← worker health tracking
│   └── queue_processor.py        ← Redis queue consumer + gRPC dispatch
├── workers/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── server.py                 ← gRPC server
│   ├── inference.py              ← Ollama call + RAG augmentation
│   └── entrypoint.sh             ← start Ollama, pull model, start server
├── rag/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── main.py                   ← FastAPI + ChromaDB queries
├── ingestion/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                   ← FastAPI ingestion service
│   ├── worker.py                 ← queue consumer + chunking + embedding
│   └── bootstrap.py              ← seeds ChromaDB from corpus/
├── client/
│   ├── locustfile.py             ← load test scenarios
│   ├── chaos.py                  ← chaos testing script
│   └── plot_results.py           ← generate report graphs
├── monitoring/
│   ├── prometheus.yml            ← scrape config
│   └── grafana/
│       └── provisioning/
│           ├── datasources/
│           │   └── prometheus.yml
│           └── dashboards/
│               └── inference.json
├── corpus/
│   └── *.txt                     ← seed documents for RAG
└── docs/
    ├── PROJECT_PLAN.md
    ├── ARCHITECTURE.md
    ├── DECISIONS.md
    └── superpowers/specs/
        └── 2026-04-26-full-system-design.md  ← this file
```

---

## 10. Docker Compose Services Summary

| Service | Image | Port | Depends On |
|---|---|---|---|
| `load-balancer` | `./load_balancer` | 8000 | master, redis |
| `master` | `./master` | 8001 | redis, worker-1..4 |
| `worker-1` | `./workers` | 9001 (gRPC) | rag-retriever |
| `worker-2` | `./workers` | 9002 (gRPC) | rag-retriever |
| `worker-3` | `./workers` | 9003 (gRPC) | rag-retriever |
| `worker-4` | `./workers` | 9004 (gRPC) | rag-retriever |
| `rag-retriever` | `./rag` | 8002 | chromadb |
| `ingestion-service` | `./ingestion` | 8003 | redis |
| `ingestion-worker-1` | `./ingestion` | — | redis, chromadb |
| `ingestion-worker-2` | `./ingestion` | — | redis, chromadb |
| `chromadb` | `chromadb/chroma` | 8004 | — |
| `redis` | `redis:7-alpine` | 6379 | — |
| `prometheus` | `prom/prometheus` | 9090 | all services |
| `grafana` | `grafana/grafana` | 3000 | prometheus |

---

## 11. Implementation Phases

| Phase | What Gets Built | When Done |
|---|---|---|
| **1 — Skeleton** | docker-compose.yml, all Dockerfiles, /health + /metrics stubs, all services start successfully | All containers green in `docker compose ps` |
| **2 — Inference Pipeline** | LB strategies, master dispatch, gRPC workers, Ollama integration, end-to-end single request works | `curl localhost:8000/infer` returns an AI response |
| **3 — RAG + Ingestion** | ChromaDB integration, ingestion pipeline, bootstrap corpus, workers use RAG context | Responses include retrieved context |
| **4 — Fault Tolerance + Monitoring** | Circuit breakers, heartbeats, retries, Prometheus + Grafana live | Kill a worker, Grafana shows recovery |
| **5 — Load Testing + Chaos** | Locust scenarios, chaos script, all metrics gathered, matplotlib graphs | Grafana shows 1000+ users, graphs in docs/ |
| **6 — Report + Demo** | Written report, YouTube video, slides | Submitted |

---

## 12. Decisions Log

| Date | Decision | Alternatives | Reason |
|---|---|---|---|
| 2026-04-26 | Use gRPC for master↔worker communication | REST HTTP, ZeroMQ | Production-grade, strongly typed, demonstrates wider reading |
| 2026-04-26 | Semantic cache in load balancer (not master) | Cache in workers, separate cache service | LB is the first touch point; caching here avoids master entirely on hits |
| 2026-04-26 | Circuit breakers in master (not workers) | Per-worker self-management | Master has global view of all workers; better for rerouting decisions |
| 2026-04-26 | Extras: circuit breakers + adaptive routing + semantic cache | Batching, priority queues, chaos tool | Best combination for grade marks: each has academic references, each is measurable, all integrate cleanly |
| 2026-04-26 | phi3:mini as LLM model | qwen2.5:3b, llama3 | Smallest model that gives coherent responses, fastest on CPU |

---

*This document is the authoritative design spec. All implementation should conform to it. Update DECISIONS.md when deviating from anything written here.*
