# CSE354 Distributed Computing Project

## Project Overview

Building a distributed system that handles **1000+ concurrent LLM inference requests** with RAG (Retrieval-Augmented Generation), efficient load balancing across simulated GPU workers, and fault tolerance.

This is a group project for Ain Shams University, Faculty of Engineering, CSE354 — 2nd Semester 2025/2026. Worth 35 marks. Deliverables: code, written report, YouTube demo video, presentation, and live discussion.

## Target Grade Band

**89%+ (highest band).** This means:
- Genuine distributed architecture (real services over a network, not threads in one process)
- Originality and independent thinking beyond the spec
- Wider reading evidence — cite real systems (vLLM, Ray Serve, NVIDIA Triton) and papers
- Professional engineering: trade-off analysis, metrics, graphs, honest limitations

Decisions and code should be justified with reasoning, not just "it works."

## Tech Stack (Locked — Do Not Re-litigate)

| Concern | Choice | Reason |
|---|---|---|
| Language | Python 3.11+ | Required by spec; ecosystem fit |
| LLM runtime | Ollama with `phi3:mini` or `qwen2.5:3b` | Real local LLM, runs on CPU/GPU |
| Vector DB | ChromaDB (Docker container) | Easy setup, runs as separate service |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` | Small, fast, industry standard |
| Internal RPC | gRPC | Production-grade, demonstrates wider reading |
| Edge API | FastAPI | For load balancer + admin endpoints |
| Queue / heartbeats | Redis | Simpler than RabbitMQ, sufficient |
| Monitoring | Prometheus + Grafana | Professional observability story |
| Load testing | Locust | Real tool, handles 1000+ users, has UI |
| Orchestration | Docker Compose | One-command stack bring-up |

**Do NOT use:** Supabase, Pinecone, OpenAI API, Kubernetes (mention in report only), Kafka, TensorFlow, hosted services in general. The project must be self-contained and demonstrably built by us.

## Architecture

```
Client (Locust, 1000+ users)
        │
        ▼
Load Balancer  ──► [Round Robin | Least Connections | Load-Aware]
        │
        ▼
Master / Coordinator  ──► tracks workers, retries, request queue
        │
        ▼
GPU Worker 1..N  ──► Ollama inference + RAG context
        │
        ▼
RAG Service  ──► ChromaDB (vector store)
        ▲
        │
Ingestion Service  ──► Ingestion Workers ──► chunking + embedding
```

### Services in `docker-compose.yml`

- `load-balancer` (FastAPI, public port 8000)
- `master` (FastAPI + gRPC)
- `worker-1` … `worker-4` (gRPC, each with Ollama)
- `rag-retriever` (FastAPI, queries ChromaDB)
- `ingestion-service` (FastAPI, accepts documents)
- `ingestion-worker-1`, `ingestion-worker-2` (consume Redis queue, embed, write to Chroma)
- `chromadb`
- `redis`
- `prometheus`
- `grafana`

## Repository Structure

```
.
├── CLAUDE.md                      ← this file
├── docker-compose.yml
├── docs/
│   ├── PROJECT_PLAN.md            ← full planning notes
│   ├── INGESTION_DESIGN.md        ← document ingestion pipeline design
│   ├── ARCHITECTURE.md            ← detailed architecture + diagrams
│   └── REPORT.md                  ← growing draft of the final report
├── common/                        ← shared models, protos, utils
├── load_balancer/
├── master/
├── workers/
├── rag/
├── ingestion/
├── client/                        ← Locust load test scripts
├── monitoring/                    ← Prometheus config, Grafana dashboards
└── corpus/                        ← documents to ingest
```

## Key Design Principles

1. **Each component is a separate service** running in its own container — never combine them into one process for convenience.
2. **All inter-service communication is over the network** (gRPC or HTTP) — no in-process function calls between services.
3. **Async wherever possible** — FastAPI async endpoints, async Redis client, async HTTP calls.
4. **Every service exposes `/metrics`** for Prometheus.
5. **Every service exposes `/health`** for liveness checks.
6. **All configuration via environment variables**, never hardcoded.
7. **No request is silently dropped** — failures must be retried or surfaced.

## Originality Features ("Extras") to Implement

Pick 2–3, not all. Each must be discussed in the report with references.

- [ ] **Continuous batching** on workers (cite vLLM paper)
- [ ] **Adaptive load-aware routing** based on rolling p95 latency
- [ ] **Priority queues** for tiered request handling
- [ ] **Semantic caching** of LLM responses (embedding similarity)
- [ ] **Circuit breakers** (closed/open/half-open) per worker
- [ ] **Chaos testing** script (random kill/slow/partition workers)

## Coding Conventions

- Python: PEP 8, type hints required on public functions, `ruff` for linting
- Async: prefer `async def` for any I/O-bound code
- Logging: structured logging via `structlog` or stdlib with consistent fields
- Errors: never bare `except:` — always specific exception types
- Tests: at least basic unit tests per service in `tests/` subfolder
- Commits: conventional commits format (`feat:`, `fix:`, `docs:`, `refactor:`)
- Branches: `feature/<service>-<short-desc>`, PR to `main`

## Performance Targets (for the Report)

Measure and report:
- **Latency:** p50, p95, p99 under load
- **Throughput:** requests/sec sustained
- **Worker utilization:** % of time workers are busy
- **Failure recovery time:** ms from worker death to request reassignment
- **Comparison:** all 3 LB strategies on identical workload
- **Scaling curve:** 100 / 500 / 1000 / 1500 concurrent users

Generate matplotlib graphs for all of the above.

## Phase Plan

| Phase | Focus | Duration |
|---|---|---|
| 1 | Architecture, Docker Compose skeleton, all services say "hello" | Week 1 |
| 2 | Load balancer (3 strategies), worker + Ollama, end-to-end single request | Week 2 |
| 3 | RAG retriever, ChromaDB integration, ingestion pipeline | Week 3 |
| 4 | Fault tolerance, heartbeats, retries, monitoring stack | Week 4 |
| 5 | Load testing, chaos testing, all metrics gathered | Week 5 |
| 6 | Report writing, demo video, presentation | Week 6 |

## Team Ownership

Adjust to your group's actual size. Suggested split:

- **Person A:** Load balancer + monitoring (Prometheus/Grafana)
- **Person B:** Master/coordinator + Redis queue + fault tolerance
- **Person C:** Workers + Ollama integration + (optional) batching
- **Person D:** RAG retriever + ingestion service + corpus prep
- **Person E:** Client/load testing + DevOps glue + report coordination

## When Working with Claude Code

- Read `docs/PROJECT_PLAN.md` for the full planning context before starting any new component.
- Always check `docker-compose.yml` to see what services already exist before adding new ones.
- When adding a new service: create the folder, add a `Dockerfile`, add the service entry to `docker-compose.yml`, expose `/health` and `/metrics`, write at minimum a "hello world" endpoint, then commit before adding business logic.
- Don't introduce new dependencies without updating the table above.
- For any non-trivial decision, write a short note in `docs/DECISIONS.md` (date, decision, alternatives considered, reason).

## References to Cite in the Report

Start collecting these now:

- vLLM paper (Kwon et al., "Efficient Memory Management for LLM Serving with PagedAttention")
- Ray Serve documentation
- NVIDIA Triton Inference Server docs
- Martin Fowler's Circuit Breaker pattern writeup
- Netflix Chaos Engineering blog posts
- Google SRE Book (chapters on load balancing and overload)
- Discord / Uber / Cloudflare scaling engineering blog posts
- ChromaDB and sentence-transformers official docs

Target: 8–10 quality references in the final report.

## Final Deliverables Checklist

- [ ] Working code in this repo
- [ ] `docker-compose up` brings up the entire system
- [ ] Locust test demonstrates 1000+ concurrent users
- [ ] Grafana dashboard shows live metrics
- [ ] Chaos test demonstrates fault tolerance with measurable recovery time
- [ ] Written report (analysis, design, testing, limitations, references)
- [ ] YouTube demo video (~10–15 min, shows ingestion → load test → failure recovery)
- [ ] Presentation slides
- [ ] Ready for live discussion
