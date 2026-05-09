# Runbook — Day-of-Demo Operations

All commands run from the project root on the **manager laptop** unless noted.

---

## 1. Start the Stack

```powershell
docker swarm init
docker stack deploy -c docker-stack.yml inference
```

Check everything is up:
```powershell
docker service ls
```

---

## 2. Add Other Laptops (Workers Only)

On each extra laptop — `git pull` the repo first, then open **admin PowerShell**:

**Node 2 (John) — workers 9-16:**
```powershell
# 1. Open firewall ports
netsh advfirewall firewall add rule name="Docker Workers" protocol=TCP dir=in localport=9009-9016 action=allow
netsh advfirewall firewall add rule name="Docker Worker Metrics" protocol=TCP dir=in localport=8089-8096 action=allow

# 2. Build the worker image
docker build -t localhost/worker:latest -f workers/Dockerfile .

# 3. Start workers
$env:MANAGER_IP="<YOUR_IP>"
$env:NODE_IP="<JOHN_IP>"
docker compose -f docker-compose.worker.yml up
```

**Node 3 — workers 17-24:**
```powershell
netsh advfirewall firewall add rule name="Docker Workers" protocol=TCP dir=in localport=9017-9024 action=allow
netsh advfirewall firewall add rule name="Docker Worker Metrics" protocol=TCP dir=in localport=8097-8104 action=allow

docker build -t localhost/worker:latest -f workers/Dockerfile .

$env:MANAGER_IP="<YOUR_IP>"
$env:NODE_IP="<NODE3_IP>"
docker compose -f docker-compose.worker3.yml up
```

**Node 4 — workers 25-32:**
```powershell
netsh advfirewall firewall add rule name="Docker Workers" protocol=TCP dir=in localport=9025-9032 action=allow
netsh advfirewall firewall add rule name="Docker Worker Metrics" protocol=TCP dir=in localport=8105-8112 action=allow

docker build -t localhost/worker:latest -f workers/Dockerfile .

$env:MANAGER_IP="<YOUR_IP>"
$env:NODE_IP="<NODE4_IP>"
docker compose -f docker-compose.worker4.yml up
```

After adding a node update its IP in `monitoring/prometheus.yml` then reload:
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

## 4. Stop Everything

```powershell
# Stop stack only (keeps swarm)
docker stack rm inference

# Full reset (stop + leave swarm)
docker stack rm inference
docker swarm leave --force
```

---

## 5. Rebuild & Redeploy a Service

```powershell
docker build -t localhost/load-balancer:latest -f load_balancer/Dockerfile .
docker service update --force --image localhost/load-balancer:latest inference_load-balancer

docker build -t localhost/master:latest -f master/Dockerfile .
docker service update --force --image localhost/master:latest inference_master

docker build -t localhost/worker:latest -f workers/Dockerfile .
docker service update --force --image localhost/worker:latest inference_worker
```
