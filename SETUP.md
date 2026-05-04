# Setup Guide

How to clone this repo and get the system running on a fresh machine. Tested on Windows 11 with Docker Desktop. The same instructions work on macOS / Linux with `docker compose` (paths obviously differ).

## Prerequisites

| Tool | Version | Why |
|---|---|---|
| Docker Desktop | 4.x or newer | Runs all 16 containers |
| WSL 2 (Windows only) | latest | Docker Desktop's backend on Windows |
| Git for Windows | any recent | Clone the repo |
| Python 3.9+ | for Locust load testing | Optional but recommended |
| A Groq account | free | Required for the Groq API key (no credit card) |

If `wsl --status` says "WSL is not installed," run `wsl --install` in an **administrator** PowerShell, then reboot. Launch Docker Desktop after the reboot and wait for "Engine running."

## Step 1 — Get a Groq API key

The system uses Groq (OpenAI-compatible fast inference) for LLM calls (free tier, no card required, 14400 req/day quota).

1. Go to <https://console.groq.com>
2. Sign in (Google / GitHub / email — no credit card required)
3. Left sidebar → **API Keys** → **Create API Key**
4. Copy the key (starts with `gsk_...`) and keep it private

> **Note on history:** This repo originally used Ollama (local phi3:mini model — slow + 2GB download, build issues), then migrated to xAI Grok (no free tier required payment), and is now on Groq for the team's free-tier-friendly chaos testing. Pull requests welcome.

## Step 2 — Clone the repo

```powershell
cd "D:\path\to\your\projects"
git clone https://github.com/Michael-Maged/-simulated-AI-inference-system.git inference-system
cd inference-system
```

The leading dash in the GitHub repo name confuses some CLI tools, so we rename the local folder to `inference-system`.

## Step 3 — Configure `.env`

```powershell
copy .env.example .env
notepad .env
```

The `.env` file should contain **exactly** these two non-comment lines:

```
GROQ_API_KEY=gsk_YOUR_KEY_HERE
GROK_MODEL=llama-3.1-8b-instant
```

That's it. No `curl` examples, no quotes, no `Bearer` prefix. Save and close.

> The env-var name is `GROK_MODEL` (without the Q) for legacy reasons — don't rename it without updating `workers/inference.py` and `docker-compose.yml` too.

Verify safely (without printing the key):

```powershell
Get-Content .env | ForEach-Object { if ($_ -match '^([A-Z_]+)=(.+)$') { "$($Matches[1])=<$($Matches[2].Length) chars, starts with $($Matches[2].Substring(0, [Math]::Min(7, $Matches[2].Length)))...>" } else { $_ } }
```

You should see `GROQ_API_KEY=<56 chars, starts with gsk_...>`.

## Step 4 — Build the shared base image

The Dockerfiles for `load-balancer`, `rag-retriever`, and `ingestion` all start with `FROM inference-base:latest`. That image has `profiles: ["build-base"]` in `docker-compose.yml`, which means a normal `docker compose up --build` won't build it. You must build it explicitly first:

```powershell
docker compose --profile build-base build inference-base
```

Takes 2-5 minutes (downloads ~500 MB of sentence-transformers + PyTorch). When done, the last log line will say `naming to docker.io/library/inference-base:latest`.

## Step 5 — Bring up the full stack

```powershell
docker compose up --build
```

First time, this takes 5-10 minutes (pulls Redis, ChromaDB, Prometheus, Grafana from Docker Hub, then builds the four Python services on top of `inference-base`). The terminal stays open and streams logs from all 16 containers.

Wait for these readiness signals (in any order):

- `redis-1 ... Ready to accept connections`
- `chromadb-1 ... Application startup complete`
- `rag-retriever-1 ... Application startup complete`
- `bootstrap-1 ... ingested N chunks` then `bootstrap-1 exited with code 0` (this is **good** — bootstrap is one-shot)
- `master-1 ... Application startup complete`
- `worker-1 ... gRPC server listening on :9001` (and 2, 3, 4)
- `load-balancer-1 ... Application startup complete`

When you see the load-balancer line, the system is ready.

## Step 6 — Smoke test

Open a **second** PowerShell tab in VS Code (the first is busy streaming logs). `cd` back into the project folder, then:

```powershell
Invoke-RestMethod -Uri http://localhost:8000/infer -Method POST -ContentType "application/json" -Body '{"prompt": "What is a circuit breaker in distributed systems?", "max_tokens": 100}'
```

Expected: 1-3 seconds, JSON with `response`, `cached: false`, `worker_id`. Send the same prompt with slightly different wording and the second call should return `cached: true` in <100ms.

Open Grafana at <http://localhost:3000> (login `admin` / `admin`) — the "Inference" dashboard auto-loads.

## Step 7 — Run a load test

Install Locust on the host machine:

```powershell
pip install locust
$env:PATH += ";$env:APPDATA\Python\Python314\Scripts"   # adjust Python version
```

Run a 50-user / 60-second test:

```powershell
mkdir docs\results -ErrorAction SilentlyContinue
locust -f client/locustfile.py --host=http://localhost:8000 --users 50 --spawn-rate 10 --run-time 60s --headless --csv=docs/results/run1
```

Watch the live dashboard while it runs. Results land in `docs/results/run1_*.csv`.

Switch load-balancing strategy mid-flight via the admin endpoint:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/admin/strategy?strategy=round_robin" -Method PUT
Invoke-RestMethod -Uri "http://localhost:8000/admin/strategy?strategy=least_connections" -Method PUT
Invoke-RestMethod -Uri "http://localhost:8000/admin/strategy?strategy=load_aware" -Method PUT
```

## Step 8 — Stop / restart

To stop the stack:

```powershell
# In the terminal running docker compose up:
Ctrl+C
docker compose down
```

To start again later (no rebuild needed if no code changed):

```powershell
docker compose up
```

## Troubleshooting

### "Docker Desktop is unable to start"
Open the Docker Desktop GUI app from the Start menu and wait for "Engine running" in the bottom-left. If it crashes, check `wsl --status` — you may need `wsl --update` or `wsl --install`.

### `inference-base:latest` not found
You skipped Step 4. Run `docker compose --profile build-base build inference-base`.

### Workers boot but every request returns 502
Their `/infer` calls are failing. Check:

1. **Is `.env` correct?** `Get-Content .env` should show `GEMINI_API_KEY=...`. Common mistakes: pasted curl example into `.env`, key has trailing whitespace, key is `your_gemini_api_key_here` placeholder.
2. **Did you restart after changing `.env`?** `docker compose restart` does NOT re-read `.env` — only `docker compose up -d --force-recreate worker-1 worker-2 worker-3 worker-4` (or `down` then `up`) re-applies env vars.
3. **What's the actual error?**
   ```powershell
   docker compose logs --since=2m worker-1 | Select-String -Pattern "ERROR|403|404|429"
   ```
   - `401 Unauthorized` → bad/missing key
   - `404 Not Found` → the model name doesn't exist; check current Groq models at <https://console.groq.com/docs/models> and update `GROK_MODEL` in `.env`
   - `429 Too Many Requests` → free-tier rate limit hit (30 req/min, 14400 req/day on `llama-3.1-8b-instant`)

### Master returns 503 with "All retries exhausted"
At least one worker is throwing on `/Infer`. See above — most likely an LLM-side error. The master is doing its job (retrying across 4 workers, then giving up cleanly).

### Workers show `circuit_state: open` in `/workers`
Five consecutive failures tripped the circuit. Wait 30 seconds for it to transition to `half_open` and self-test, or restart the worker:
```powershell
docker compose restart worker-2
```

### Locust says `locust: command not found`
Pip installed `locust.exe` to a folder not on PATH. For the current session:
```powershell
$env:PATH += ";$env:APPDATA\Python\Python314\Scripts"
```
For permanent fix, append that path to your user PATH via System Properties.

### Git shows ~50 modified files immediately after clone
Line-ending difference (LF in repo, CRLF on Windows checkout). Harmless — Docker doesn't care. Ignore.

### `curl` behaves weirdly in PowerShell
PowerShell aliases `curl` to `Invoke-WebRequest` with different syntax. Use `Invoke-RestMethod` for JSON APIs (returns parsed objects) or type `curl.exe` to force the real curl if installed.

## Service Map

| Service | Port | What it does |
|---|---|---|
| load-balancer | **8000** | Public API — send requests here |
| master | 8001 | Coordinator — manages workers |
| rag-retriever | 8002 | Retrieves context from ChromaDB |
| ingestion-service | 8003 | Accepts new documents |
| chromadb | 8004 | Vector database |
| worker-1 | 9001 | gRPC AI worker |
| worker-2 | 9002 | gRPC AI worker |
| worker-3 | 9003 | gRPC AI worker |
| worker-4 | 9004 | gRPC AI worker |
| redis | 6379 | Queue, cache, heartbeats |
| prometheus | 9090 | Metrics collector |
| **grafana** | **3000** | **Live dashboard** (admin/admin) |
