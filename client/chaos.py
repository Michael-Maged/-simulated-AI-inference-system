"""
Chaos testing script. Run while Locust is active.

Usage:
  python client/chaos.py --status
  python client/chaos.py --kill worker-2
  python client/chaos.py --recover worker-2
  python client/chaos.py --slow worker-3 500
  python client/chaos.py --scale 6

Notes:
  --kill / --recover work on Swarm workers (1-8) only.
  --slow works on any locally running container found by WORKER_ID env var.
"""
import argparse
import subprocess
import sys
import httpx


def _swarm_replicas() -> int:
    result = subprocess.run(
        ["docker", "service", "ls", "--filter", "name=inference_worker", "--format", "{{.Replicas}}"],
        capture_output=True, text=True,
    )
    s = result.stdout.strip()
    return int(s.split("/")[-1]) if s else 0


def _find_container(worker_id: str) -> str:
    """Find container ID by WORKER_ID env var — works for both Swarm and Compose."""
    result = subprocess.run(
        ["docker", "ps", "--format", "{{.ID}} {{.Names}}"],
        capture_output=True, text=True,
    )
    for line in result.stdout.strip().splitlines():
        parts = line.split(" ", 1)
        if len(parts) < 2:
            continue
        cid = parts[0]
        env = subprocess.run(
            ["docker", "exec", cid, "sh", "-c", "echo $WORKER_ID"],
            capture_output=True, text=True,
        )
        if env.stdout.strip() == worker_id:
            return cid
    return ""


def kill_worker(worker_id: str):
    current = _swarm_replicas()
    if current <= 1:
        print("Only 1 Swarm worker left — won't kill the last one.", flush=True)
        sys.exit(1)
    print(f"Scaling Swarm workers down from {current} to {current - 1}...", flush=True)
    subprocess.run(["docker", "service", "scale", f"inference_worker={current - 1}"], check=True)
    print(f"Done. Master marks {worker_id} dead in ~15s. Watch Grafana.", flush=True)


def recover_worker(worker_id: str):
    current = _swarm_replicas()
    print(f"Scaling Swarm workers up from {current} to {current + 1}...", flush=True)
    subprocess.run(["docker", "service", "scale", f"inference_worker={current + 1}"], check=True)
    print(f"Done. New worker will register in ~10s. Circuit breaker → HALF_OPEN after 30s.", flush=True)


def scale(count: int):
    subprocess.run(["docker", "service", "scale", f"inference_worker={count}"], check=True)
    print(f"Scaled Swarm workers to {count}.", flush=True)


def slow_worker(worker_id: str, delay_ms: int):
    print(f"Looking for container with WORKER_ID={worker_id}...", flush=True)
    cid = _find_container(worker_id)
    if not cid:
        print(f"Container for {worker_id} not found locally.", flush=True)
        sys.exit(1)
    subprocess.run([
        "docker", "exec", "--privileged", cid,
        "sh", "-c",
        f"tc qdisc del dev eth0 root 2>/dev/null || true && "
        f"tc qdisc add dev eth0 root netem delay {delay_ms}ms"
    ], check=True)
    print(f"Added {delay_ms}ms network delay to {worker_id}.", flush=True)


def status():
    try:
        resp = httpx.get("http://localhost:8001/workers", timeout=15.0)
        workers = resp.json()
        print(f"\n{'Worker':<15} {'Alive':<8} {'Circuit':<12} {'Queue':<8} {'Latency ms'}")
        print("-" * 60)
        for w in workers:
            print(
                f"{w['worker_id']:<15} {str(w['alive']):<8} {w['circuit_state']:<12} "
                f"{w['queue_depth']:<8} {w['last_latency_ms']:.0f}"
            )
        swarm = _swarm_replicas()
        print(f"\nSwarm workers: {swarm}   Total registered: {len(workers)}")
    except Exception as e:
        print(f"Error reaching master: {e}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Chaos testing for inference system")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--kill",    metavar="WORKER_ID",               help="Scale Swarm down by 1")
    group.add_argument("--recover", metavar="WORKER_ID",               help="Scale Swarm up by 1")
    group.add_argument("--slow",    nargs=2, metavar=("WORKER_ID", "DELAY_MS"), help="Add network delay to a container")
    group.add_argument("--scale",   metavar="N", type=int,             help="Set exact Swarm worker count")
    group.add_argument("--status",  action="store_true",               help="Show all worker statuses")
    args = parser.parse_args()

    if args.kill:
        kill_worker(args.kill)
    elif args.recover:
        recover_worker(args.recover)
    elif args.slow:
        slow_worker(args.slow[0], int(args.slow[1]))
    elif args.scale is not None:
        scale(args.scale)
    elif args.status:
        status()
