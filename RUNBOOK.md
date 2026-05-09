# Runbook — Day-of-Demo Operations

All commands run from the project root on the **manager laptop** unless noted.

---

## 1. Start the Stack

```powershell
docker swarm init
docker stack deploy -c docker-stack.yml inference
```

Check everything is up (all replicas should match):
```powershell
docker service ls
```

---

## 2. Add Other Laptops (Workers Only)

On each extra laptop — open admin PowerShell:

**Node 2 (John) — workers 9-16:**
```powershell
netsh advfirewall firewall add rule name="Docker Workers" protocol=TCP dir=in localport=9009-9016 action=allow
netsh advfirewall firewall add rule name="Docker Worker Metrics" protocol=TCP dir=in localport=8089-8096 action=allow
$env:MANAGER_IP="<YOUR_IP>"
$env:NODE_IP="<JOHN_IP>"
docker compose -f docker-compose.worker.yml up
```

**Node 3 — workers 17-24:**
```powershell
netsh advfirewall firewall add rule name="Docker Workers" protocol=TCP dir=in localport=9017-9024 action=allow
netsh advfirewall firewall add rule name="Docker Worker Metrics" protocol=TCP dir=in localport=8097-8104 action=allow
$env:MANAGER_IP="<YOUR_IP>"
$env:NODE_IP="<NODE3_IP>"
docker compose -f docker-compose.worker3.yml up
```

**Node 4 — workers 25-32:**
```powershell
netsh advfirewall firewall add rule name="Docker Workers" protocol=TCP dir=in localport=9025-9032 action=allow
netsh advfirewall firewall add rule name="Docker Worker Metrics" protocol=TCP dir=in localport=8105-8112 action=allow
$env:MANAGER_IP="<YOUR_IP>"
$env:NODE_IP="<NODE4_IP>"
docker compose -f docker-compose.worker4.yml up
```

After adding a node, update `monitoring/prometheus.yml` with its IP, then reload:
```powershell
Invoke-RestMethod -Uri "http://localhost:9090/-/reload" -Method POST
```

---

## 3. Before Every Test

```powershell
# 1. Flush in-flight queue counters
Invoke-RestMethod -Uri "http://localhost:8001/admin/flush" -Method POST

# 2. Clear semantic cache
Invoke-RestMethod -Uri "http://localhost:8000/admin/cache" -Method DELETE

# 3. Verify all workers alive and queue is 0
Invoke-RestMethod -Uri "http://localhost:8001/workers" | ConvertTo-Json -Depth 2
```

---

## 4. Load Tests

```powershell
# Smoke test — 20 users, 2 min
locust -f client/locustfile.py --host http://localhost:8000 --users 20 --spawn-rate 2 --run-time 2m --headless

# Standard — 100 users, 5 min
locust -f client/locustfile.py --host http://localhost:8000 --users 100 --spawn-rate 5 --run-time 5m --headless

# Medium — 500 users, 10 min
locust -f client/locustfile.py --host http://localhost:8000 --users 500 --spawn-rate 20 --run-time 10m --headless

# Peak — 1000 users, 10 min (saves CSV for graphs)
locust -f client/locustfile.py --host http://localhost:8000 --users 1000 --spawn-rate 50 --run-time 10m --headless --csv client/results/peak_1000

# Stress — 1500 users
locust -f client/locustfile.py --host http://localhost:8000 --users 1500 --spawn-rate 50 --run-time 10m --headless --csv client/results/stress_1500

# Web UI (open http://localhost:8089)
locust -f client/locustfile.py --host http://localhost:8000
```

---

## 5. Change Load Balancing Strategy

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

### Strategy Comparison (run back-to-back)

```powershell
# Round Robin
Invoke-RestMethod -Uri "http://localhost:8001/admin/flush" -Method POST
Invoke-RestMethod -Uri "http://localhost:8000/admin/cache" -Method DELETE
Invoke-RestMethod -Uri "http://localhost:8000/admin/strategy?strategy=round_robin" -Method PUT
locust -f client/locustfile.py --host http://localhost:8000 --users 200 --spawn-rate 10 --run-time 3m --headless --csv client/results/round_robin

# Least Connections
Invoke-RestMethod -Uri "http://localhost:8001/admin/flush" -Method POST
Invoke-RestMethod -Uri "http://localhost:8000/admin/cache" -Method DELETE
Invoke-RestMethod -Uri "http://localhost:8000/admin/strategy?strategy=least_connections" -Method PUT
locust -f client/locustfile.py --host http://localhost:8000 --users 200 --spawn-rate 10 --run-time 3m --headless --csv client/results/least_connections

# Load-Aware
Invoke-RestMethod -Uri "http://localhost:8001/admin/flush" -Method POST
Invoke-RestMethod -Uri "http://localhost:8000/admin/cache" -Method DELETE
Invoke-RestMethod -Uri "http://localhost:8000/admin/strategy?strategy=load_aware" -Method PUT
locust -f client/locustfile.py --host http://localhost:8000 --users 200 --spawn-rate 10 --run-time 3m --headless --csv client/results/load_aware
```

---

## 6. Scale Workers

```powershell
# Scale your swarm workers up or down
docker service scale inference_worker=4
docker service scale inference_worker=8

# Check worker count and status
Invoke-RestMethod -Uri "http://localhost:8001/workers" | ConvertTo-Json -Depth 2
```

---

## 7. Chaos Testing

Run while a load test is active in another terminal.

```powershell
# Check all worker statuses
python client/chaos.py --status

# Kill a worker (scales down by 1)
python client/chaos.py --kill worker-2

# Add 500ms network delay to a worker
python client/chaos.py --slow worker-3 500

# Recover (scales back up by 1)
python client/chaos.py --recover worker-2

# Set exact worker count
python client/chaos.py --scale 6
```

---

## 8. Cache Management

```powershell
# Check cache status (enabled/disabled + entry count)
Invoke-RestMethod -Uri "http://localhost:8000/admin/cache/status"

# Clear all cached responses
Invoke-RestMethod -Uri "http://localhost:8000/admin/cache" -Method DELETE

# Enable cache
Invoke-RestMethod -Uri "http://localhost:8000/admin/cache/toggle?enabled=true" -Method PUT

# Disable cache (use for load testing — cache hides real scaling behavior)
Invoke-RestMethod -Uri "http://localhost:8000/admin/cache/toggle?enabled=false" -Method PUT
```

---

## 9. Monitor GPU Usage

```powershell
# Watch your GPU utilization live (run in separate terminal during test)
$cid = docker ps --filter name=inference_ollama --format "{{.ID}}"
docker exec $cid nvidia-smi dmon -s u -d 2
```

---

## 10. Monitoring URLs

| URL | What |
|---|---|
| http://localhost:3000 | Grafana (admin / admin) |
| http://localhost:9090/targets | Prometheus scrape targets |
| http://localhost:8001/workers | All worker statuses |
| http://localhost:8000/health | Load balancer health |

---

## 11. Logs

```powershell
docker service logs inference_load-balancer --tail 30
docker service logs inference_master --tail 30
docker service logs inference_worker --tail 30
docker service logs inference_ollama --tail 30
```

---

## 12. Stop Everything

```powershell
# Stop stack only (keeps swarm)
docker stack rm inference

# Full reset (stop + leave swarm)
docker stack rm inference
docker swarm leave --force
```

---

## 13. Rebuild & Redeploy a Service

```powershell
docker build -t localhost/load-balancer:latest -f load_balancer/Dockerfile .
docker service update --force --image localhost/load-balancer:latest inference_load-balancer

docker build -t localhost/master:latest -f master/Dockerfile .
docker service update --force --image localhost/master:latest inference_master

docker build -t localhost/worker:latest -f workers/Dockerfile .
docker service update --force --image localhost/worker:latest inference_worker
```
