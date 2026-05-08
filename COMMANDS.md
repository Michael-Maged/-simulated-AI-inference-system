# Commands

All commands run from the project root.

---

## Start / Stop

```powershell
# First time (builds images)
docker compose up --build

# Every time after
docker compose up

# Stop
docker compose down

# Swarm — deploy / update
docker stack deploy -c docker-stack.yml inference

# Swarm — tear down
docker stack rm inference
```

---

## Before Every Test

```powershell
# 1. Flush in-flight queue
Invoke-RestMethod -Uri "http://localhost:8001/admin/flush" -Method POST

# 2. Check all workers are alive and queue is 0
Invoke-RestMethod -Uri "http://localhost:8001/workers"
```

---

## Load Tests

```powershell
# Install once
pip install locust

# Quick test — 20 users
locust -f client/locustfile.py --host http://localhost:8000 --users 20 --spawn-rate 2 --run-time 2m --headless

# Standard test — 100 users
locust -f client/locustfile.py --host http://localhost:8000 --users 100 --spawn-rate 5 --run-time 5m --headless --csv client/results/test_100

# Peak test — 1000 users
locust -f client/locustfile.py --host http://localhost:8000 --users 1000 --spawn-rate 50 --run-time 10m --headless --csv client/results/test_1000

# With UI (open http://localhost:8089)
locust -f client/locustfile.py --host http://localhost:8000
```

---

## Strategy Comparison

```powershell
# Round Robin
Invoke-RestMethod -Uri "http://localhost:8001/admin/flush" -Method POST
Invoke-RestMethod -Uri "http://localhost:8000/admin/strategy?strategy=round_robin" -Method PUT
locust -f client/locustfile.py --host http://localhost:8000 --users 100 --spawn-rate 5 --run-time 3m --headless --csv client/results/round_robin

# Least Connections
Invoke-RestMethod -Uri "http://localhost:8001/admin/flush" -Method POST
Invoke-RestMethod -Uri "http://localhost:8000/admin/strategy?strategy=least_connections" -Method PUT
locust -f client/locustfile.py --host http://localhost:8000 --users 100 --spawn-rate 5 --run-time 3m --headless --csv client/results/least_connections

# Load-Aware
Invoke-RestMethod -Uri "http://localhost:8001/admin/flush" -Method POST
Invoke-RestMethod -Uri "http://localhost:8000/admin/strategy?strategy=load_aware" -Method PUT
locust -f client/locustfile.py --host http://localhost:8000 --users 100 --spawn-rate 5 --run-time 3m --headless --csv client/results/load_aware
```

---

## Chaos Test

Run while a load test is active in another terminal.

```powershell
# Worker status
python client/chaos.py --status

# Kill a worker
python client/chaos.py --kill worker-2

# Add network delay
python client/chaos.py --slow worker-3 500

# Recover
python client/chaos.py --recover worker-2
```

---

## Swarm Multi-Laptop Setup

```powershell
# On manager laptop — init swarm
docker swarm init
# Copy the join token it prints

# On each worker laptop
docker swarm join --token SWMTKN-... <manager-ip>:2377

# Check all nodes joined
docker node ls

# Scale workers (e.g. 2 per laptop × 4 laptops = 8)
docker service scale inference_worker=8

# Deploy / update stack
docker stack deploy -c docker-stack.yml inference
```

---

## Rebuild & Deploy a Service

```powershell
docker build -t localhost/load-balancer:latest -f load_balancer/Dockerfile .
docker service update --force --image localhost/load-balancer:latest inference_load-balancer

docker build -t localhost/master:latest -f master/Dockerfile .
docker service update --force --image localhost/master:latest inference_master

docker build -t localhost/worker:latest -f workers/Dockerfile .
docker service update --force --image localhost/worker:latest inference_worker
```

---

## Useful Checks

```powershell
# All services and replica counts
docker service ls

# Worker status (alive, circuit state, latency)
Invoke-RestMethod -Uri "http://localhost:8001/workers"

# Logs
docker service logs -f inference_worker
docker service logs -f inference_master
docker service logs -f inference_ollama

# Clean up dangling containers
docker system prune -f
```

---

## Monitoring

| URL | What |
|---|---|
| http://localhost:3000 | Grafana (admin / admin) |
| http://localhost:9090/targets | Prometheus — check scraped targets |
| http://localhost:8001/workers | Worker registry |
