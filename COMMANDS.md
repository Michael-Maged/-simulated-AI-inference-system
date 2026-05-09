# Commands

All commands run from the project root.

---

## Health Checks

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/health"   # Load balancer
Invoke-RestMethod -Uri "http://localhost:8001/health"   # Master
Invoke-RestMethod -Uri "http://localhost:8001/workers"  # All worker statuses
docker service ls                                        # All service replica counts
```

---

## Queue

```powershell
# Flush in-flight queue counters (run before every test)
Invoke-RestMethod -Uri "http://localhost:8001/admin/flush" -Method POST
```

---

## Cache

```powershell
# Check status
Invoke-RestMethod -Uri "http://localhost:8000/admin/cache/status"

# Clear all cached responses
Invoke-RestMethod -Uri "http://localhost:8000/admin/cache" -Method DELETE

# Enable / Disable
Invoke-RestMethod -Uri "http://localhost:8000/admin/cache/toggle?enabled=true" -Method PUT
Invoke-RestMethod -Uri "http://localhost:8000/admin/cache/toggle?enabled=false" -Method PUT
```

---

## Load Balancing Strategy

```powershell
# Check current strategy
Invoke-RestMethod -Uri "http://localhost:8000/admin/strategy"

# Switch strategy
Invoke-RestMethod -Uri "http://localhost:8000/admin/strategy?strategy=round_robin" -Method PUT
Invoke-RestMethod -Uri "http://localhost:8000/admin/strategy?strategy=least_connections" -Method PUT
Invoke-RestMethod -Uri "http://localhost:8000/admin/strategy?strategy=load_aware" -Method PUT
```

---

## Scale Workers

```powershell
docker service scale inference_worker=4
docker service scale inference_worker=8
docker service scale inference_worker=16
```

---

## Chaos Testing

Run while a load test is active in another terminal.

```powershell
# Worker status
python client/chaos.py --status

# Kill a worker (scales down by 1)
python client/chaos.py --kill worker-2

# Add network delay to a worker
python client/chaos.py --slow worker-3 500

# Recover a killed worker (scales back up by 1)
python client/chaos.py --recover worker-2

# Set exact worker count
python client/chaos.py --scale 6
```

---

## Load Tests

```powershell
# Web UI — open http://localhost:8089 (also saves CSV automatically)
locust -f client/locustfile.py --host http://localhost:8000 --csv client/results/my_test

# Headless tests
locust -f client/locustfile.py --host http://localhost:8000 --users 20   --spawn-rate 2  --run-time 2m  --headless --csv client/results/scale_20
locust -f client/locustfile.py --host http://localhost:8000 --users 100  --spawn-rate 5  --run-time 5m  --headless --csv client/results/scale_100
locust -f client/locustfile.py --host http://localhost:8000 --users 500  --spawn-rate 20 --run-time 10m --headless --csv client/results/scale_500
locust -f client/locustfile.py --host http://localhost:8000 --users 1000 --spawn-rate 50 --run-time 10m --headless --csv client/results/scale_1000
locust -f client/locustfile.py --host http://localhost:8000 --users 1500 --spawn-rate 50 --run-time 10m --headless --csv client/results/scale_1500
```

### Strategy Comparison

```powershell
Invoke-RestMethod -Uri "http://localhost:8001/admin/flush" -Method POST
Invoke-RestMethod -Uri "http://localhost:8000/admin/cache" -Method DELETE
Invoke-RestMethod -Uri "http://localhost:8000/admin/strategy?strategy=round_robin" -Method PUT
locust -f client/locustfile.py --host http://localhost:8000 --users 200 --spawn-rate 10 --run-time 3m --headless --csv client/results/round_robin

Invoke-RestMethod -Uri "http://localhost:8001/admin/flush" -Method POST
Invoke-RestMethod -Uri "http://localhost:8000/admin/cache" -Method DELETE
Invoke-RestMethod -Uri "http://localhost:8000/admin/strategy?strategy=least_connections" -Method PUT
locust -f client/locustfile.py --host http://localhost:8000 --users 200 --spawn-rate 10 --run-time 3m --headless --csv client/results/least_connections

Invoke-RestMethod -Uri "http://localhost:8001/admin/flush" -Method POST
Invoke-RestMethod -Uri "http://localhost:8000/admin/cache" -Method DELETE
Invoke-RestMethod -Uri "http://localhost:8000/admin/strategy?strategy=load_aware" -Method PUT
locust -f client/locustfile.py --host http://localhost:8000 --users 200 --spawn-rate 10 --run-time 3m --headless --csv client/results/load_aware
```

---

## Generate Graphs

```powershell
pip install matplotlib pandas   # install once

# Single test overview
python client/plot_results.py --csv client/results/scale_1000

# Strategy comparison
python client/plot_results.py --compare-strategies `
  --rr client/results/round_robin `
  --lc client/results/least_connections `
  --la client/results/load_aware

# Scaling curve
python client/plot_results.py --scaling `
  client/results/scale_100 `
  client/results/scale_500 `
  client/results/scale_1000 `
  client/results/scale_1500
```

---

## Monitor GPU

```powershell
# Run in a separate terminal while test is active
$cid = docker ps --filter name=inference_ollama --format "{{.ID}}"
docker exec $cid nvidia-smi dmon -s u -d 2
```

---

## Monitoring URLs

| URL | What |
|---|---|
| http://localhost:3000 | Grafana (admin / admin) |
| http://localhost:9090/targets | Prometheus scrape targets |
| http://localhost:8001/workers | Worker registry |

---

## Logs

```powershell
docker service logs inference_load-balancer --tail 30
docker service logs inference_master --tail 30
docker service logs inference_worker --tail 30
docker service logs inference_ollama --tail 30
```
