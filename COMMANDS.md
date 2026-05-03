# Command Reference

Quick copy-paste commands for everything in the system. Run all commands from the project root unless noted.

---

## Stack

```powershell
# First time (builds images, takes 5-15 min)
docker compose up --build

# Every time after (fast)
docker compose up

# Stop everything (keeps data)
docker compose down

# Stop and wipe all volumes (fresh start)
docker compose down -v

# Rebuild and restart one service only
docker compose up -d --build load-balancer
docker compose up -d --build master
docker compose up -d --build worker-1
```

---

## Single Request

```powershell
# Send one inference request
Invoke-RestMethod -Uri "http://localhost:8000/infer" -Method POST `
  -ContentType "application/json" `
  -Body '{"prompt": "What is a circuit breaker?", "max_tokens": 100}'

# Send it again — should return cached: true instantly
Invoke-RestMethod -Uri "http://localhost:8000/infer" -Method POST `
  -ContentType "application/json" `
  -Body '{"prompt": "What is a circuit breaker?", "max_tokens": 100}'
```

---

## Cache

```powershell
# Clear all cached responses (via API — load balancer must be healthy)
Invoke-RestMethod -Uri "http://localhost:8000/admin/cache" -Method DELETE

# Clear cache directly via Redis (works even if load balancer is still starting)
docker compose exec redis redis-cli EVAL "local k=redis.call('keys','cache:embed:*') if #k>0 then return redis.call('del',unpack(k)) else return 0 end" 0

# Count how many cache entries exist
docker compose exec redis redis-cli KEYS "cache:embed:*"
```

> Clear the cache before running load tests so requests actually reach workers and produce metrics.

---

## Load Balancing Strategy

```powershell
# Check current strategy
Invoke-RestMethod -Uri "http://localhost:8000/admin/strategy"

# Switch to Round Robin
Invoke-RestMethod -Uri "http://localhost:8000/admin/strategy?strategy=round_robin" -Method PUT

# Switch to Least Connections
Invoke-RestMethod -Uri "http://localhost:8000/admin/strategy?strategy=least_connections" -Method PUT

# Switch to Load-Aware (default)
Invoke-RestMethod -Uri "http://localhost:8000/admin/strategy?strategy=load_aware" -Method PUT
```

---

## Load Tests (Locust)

Install once:
```powershell
pip install locust
```

```powershell
# Quick smoke test — 20 users, 60 seconds
locust -f client/locustfile.py --host http://localhost:8000 `
  --users 20 --spawn-rate 2 --run-time 60s --headless

# Small load — 100 users, 2 minutes
locust -f client/locustfile.py --host http://localhost:8000 `
  --users 100 --spawn-rate 5 --run-time 2m --headless

# Medium load — 500 users, 5 minutes
locust -f client/locustfile.py --host http://localhost:8000 `
  --users 500 --spawn-rate 20 --run-time 5m --headless

# Peak load — 1000 users, 10 minutes (with CSV output for graphs)
locust -f client/locustfile.py --host http://localhost:8000 `
  --users 1000 --spawn-rate 50 --run-time 10m --headless `
  --csv client/results/peak_1000

# 1500 users (stress test)
locust -f client/locustfile.py --host http://localhost:8000 `
  --users 1500 --spawn-rate 50 --run-time 10m --headless `
  --csv client/results/stress_1500

# With Locust web UI (open http://localhost:8089 to control it)
locust -f client/locustfile.py --host http://localhost:8000
```

### Strategy Comparison Tests

Run these back-to-back, clearing cache before each:

```powershell
# Round Robin test
Invoke-RestMethod -Uri "http://localhost:8000/admin/cache" -Method DELETE
Invoke-RestMethod -Uri "http://localhost:8000/admin/strategy?strategy=round_robin" -Method PUT
locust -f client/locustfile.py --host http://localhost:8000 `
  --users 200 --spawn-rate 10 --run-time 3m --headless `
  --csv client/results/round_robin

# Least Connections test
Invoke-RestMethod -Uri "http://localhost:8000/admin/cache" -Method DELETE
Invoke-RestMethod -Uri "http://localhost:8000/admin/strategy?strategy=least_connections" -Method PUT
locust -f client/locustfile.py --host http://localhost:8000 `
  --users 200 --spawn-rate 10 --run-time 3m --headless `
  --csv client/results/least_connections

# Load-Aware test
Invoke-RestMethod -Uri "http://localhost:8000/admin/cache" -Method DELETE
Invoke-RestMethod -Uri "http://localhost:8000/admin/strategy?strategy=load_aware" -Method PUT
locust -f client/locustfile.py --host http://localhost:8000 `
  --users 200 --spawn-rate 10 --run-time 3m --headless `
  --csv client/results/load_aware
```

---

## Chaos Tests

Run while a Locust test is active in another terminal.

```powershell
# Check all worker statuses (alive, circuit state, queue depth, latency)
python client/chaos.py --status

# Kill a worker (circuit breaker will open, requests reroute automatically)
python client/chaos.py --kill worker-2

# Add 500ms network delay to a worker (simulates slow node)
python client/chaos.py --slow worker-3 500

# Recover a killed worker (circuit transitions OPEN → HALF-OPEN → CLOSED)
python client/chaos.py --recover worker-2

# Full chaos demo sequence
python client/chaos.py --kill worker-2
Start-Sleep 10
python client/chaos.py --status
Start-Sleep 30
python client/chaos.py --recover worker-2
python client/chaos.py --status
```

---

## Worker Management

```powershell
# Check all worker statuses (via master API)
Invoke-RestMethod -Uri "http://localhost:8001/workers"

# Restart one worker
docker compose restart worker-2

# Restart all workers
docker compose restart worker-1 worker-2 worker-3 worker-4

# Stop one worker (to simulate failure)
docker compose stop worker-3

# Start it back
docker compose start worker-3

# View live logs from one worker
docker compose logs -f worker-1

# View all worker logs together
docker compose logs -f worker-1 worker-2 worker-3 worker-4
```

---

## Generate Report Graphs

```powershell
pip install matplotlib pandas

# Generate graphs from a specific test run
python client/plot_results.py --csv-prefix client/results/peak_1000 --out client/results/

# After running all 3 strategy tests, compare them
python client/plot_results.py --csv-prefix client/results/round_robin --out client/results/
python client/plot_results.py --csv-prefix client/results/least_connections --out client/results/
python client/plot_results.py --csv-prefix client/results/load_aware --out client/results/
```

---

## Unit Tests

```powershell
pip install pytest pytest-asyncio redis numpy
pytest tests/ -v
```

---

## Health Checks

```powershell
# Check all services are up
Invoke-RestMethod -Uri "http://localhost:8000/health"   # Load balancer
Invoke-RestMethod -Uri "http://localhost:8001/health"   # Master
Invoke-RestMethod -Uri "http://localhost:8002/health"   # RAG retriever
Invoke-RestMethod -Uri "http://localhost:8003/health"   # Ingestion service

# Check container states
docker compose ps
```

---

## Monitoring

| URL | What it shows |
|---|---|
| http://localhost:3000 | Grafana dashboard (admin / admin) |
| http://localhost:9090 | Prometheus — query raw metrics |
| http://localhost:9090/targets | Which services Prometheus is scraping |

```powershell
# Useful Prometheus queries (paste into http://localhost:9090)

# Request throughput
sum(rate(lb_requests_total[1m]))

# Cache hit rate %
100 * rate(lb_cache_hits_total[5m]) / (rate(lb_cache_hits_total[5m]) + rate(lb_cache_misses_total[5m]))

# Worker p95 latency per worker
histogram_quantile(0.95, sum(rate(worker_infer_latency_seconds_bucket[5m])) by (worker_id, le))

# In-flight connections per worker
master_queue_depth

# Healthy worker count
master_workers_healthy
```

---

## Redis Inspection

```powershell
# Open Redis CLI
docker compose exec redis redis-cli

# Inside redis-cli:
KEYS *                          # see everything
KEYS cache:embed:*              # cache entries
KEYS connections:*              # in-flight per worker
KEYS queue:*                    # request queues
GET connections:worker-1        # in-flight count for worker-1
TTL cache:embed:<hash>          # seconds until a cache entry expires
```

---

## Logs

```powershell
# All services
docker compose logs -f

# One service
docker compose logs -f load-balancer
docker compose logs -f master
docker compose logs -f rag-retriever

# Last 100 lines without following
docker compose logs --tail 100 worker-1
```
