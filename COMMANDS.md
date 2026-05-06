# Command Reference

Quick copy-paste commands for everything in the system. Run all commands from the project root unless noted.

---

## Stack

```powershell
# First time setup — init swarm and deploy
docker swarm init
docker stack deploy -c docker-stack.yml inference

# Every time after (swarm already initialized)
docker stack deploy -c docker-stack.yml inference

# Stop everything
docker stack rm inference

# Fresh start (stop + leave swarm)
docker stack rm inference
docker swarm leave --force

# Check all services and replica counts
docker service ls

# Check which node each task is running on
docker stack ps inference

# Rebuild one image and update its service
docker build -t localhost/master:latest -f master/Dockerfile .
docker service update --image localhost/master:latest inference_master

docker build -t localhost/load-balancer:latest -f load_balancer/Dockerfile .
docker service update --image localhost/load-balancer:latest inference_load-balancer

docker build -t localhost/worker:latest -f workers/Dockerfile .
docker service update --image localhost/worker:latest inference_worker
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
# Clear all cached responses (via API)
Invoke-RestMethod -Uri "http://localhost:8000/admin/cache" -Method DELETE

# Clear cache directly via Redis
docker run --rm --network inference_inference-net redis:7-alpine redis-cli -h redis EVAL "local k=redis.call('keys','cache:embed:*') if #k>0 then return redis.call('del',unpack(k)) else return 0 end" 0

# Count how many cache entries exist
docker run --rm --network inference_inference-net redis:7-alpine redis-cli -h redis KEYS "cache:embed:*"
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
Invoke-RestMethod -Uri "http://localhost:8001/workers"

# Simulate worker failure — scale down
docker service scale inference_worker=2

# Watch circuit breaker trip (check after ~15 seconds)
Invoke-RestMethod -Uri "http://localhost:8001/workers"

# Recover — scale back up
docker service scale inference_worker=4

# Kill one specific worker container
docker ps --filter "name=inference_worker" --format "{{.Names}}"
docker stop <container_name>   # Swarm will auto-restart it

# Force restart all workers
docker service update --force inference_worker
```

---

## Worker Management

```powershell
# Check all worker statuses (via master API)
Invoke-RestMethod -Uri "http://localhost:8001/workers"

# Scale workers up or down
docker service scale inference_worker=4
docker service scale inference_worker=8

# Restart all workers
docker service update --force inference_worker

# View worker logs (last 20 lines)
docker service logs inference_worker --tail 20

# View master logs
docker service logs inference_master --tail 20

# View load balancer logs
docker service logs inference_load-balancer --tail 20
```

---

## Docker Swarm Multi-Node

```powershell
# Get token to add worker nodes (run on manager machine)
docker swarm join-token worker

# Check all nodes in the swarm
docker node ls

# See which node each task runs on
docker service ps inference_worker

# Remove a node from swarm (run on the node being removed)
docker swarm leave

# Force remove a node (run on manager)
docker node rm <node-id>
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

# Check swarm service states
docker service ls
docker stack ps inference
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
docker run --rm -it --network inference_inference-net redis:7-alpine redis-cli -h redis

# Inside redis-cli:
KEYS *                          # see everything
KEYS cache:embed:*              # cache entries
KEYS connections:*              # in-flight per worker
KEYS queue:*                    # request queues
TTL cache:embed:<hash>          # seconds until a cache entry expires
```

---

## Logs

```powershell
# All services (last 20 lines each)
docker service logs inference_load-balancer --tail 20
docker service logs inference_master --tail 20
docker service logs inference_rag-retriever --tail 20
docker service logs inference_worker --tail 20

# Follow logs live (warning: verbose with 4 worker replicas)
docker service logs inference_master --follow
```
