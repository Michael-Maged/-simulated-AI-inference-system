"""
Chaos testing script. Run while Locust is active.

Usage:
  python client/chaos.py --kill worker-2
  python client/chaos.py --slow worker-3 500
  python client/chaos.py --recover worker-2
  python client/chaos.py --status
  python client/chaos.py --scale 3
"""
import argparse
import subprocess
import sys
import httpx


def _find_container(worker_id: str) -> str:
    """Find container ID by WORKER_ID label — works in both Swarm and Compose."""
    # Try Swarm task name pattern first (inference_worker.N)
    result = subprocess.run(
        ["docker", "ps", "--filter", f"name=inference_worker", "--format", "{{.ID}} {{.Names}}"],
        capture_output=True, text=True
    )
    for line in result.stdout.strip().splitlines():
        cid, cname = line.split(" ", 1)
        # Check WORKER_ID env var inside the container
        env_result = subprocess.run(
            ["docker", "exec", cid, "sh", "-c", "echo $WORKER_ID"],
            capture_output=True, text=True
        )
        if env_result.stdout.strip() == worker_id:
            return cid

    # Fallback: compose-style name (worker-2)
    result = subprocess.run(
        ["docker", "ps", "--filter", f"name={worker_id}", "--format", "{{.ID}}"],
        capture_output=True, text=True
    )
    cid = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
    return cid


def kill_worker(worker_id: str):
    """Scale down by 1 — Swarm won't restart it unlike docker stop."""
    result = subprocess.run(
        ["docker", "service", "ls", "--filter", "name=inference_worker", "--format", "{{.Replicas}}"],
        capture_output=True, text=True
    )
    replicas_str = result.stdout.strip()
    current = int(replicas_str.split("/")[-1]) if replicas_str else 4
    if current <= 1:
        print("Only 1 worker left — won't kill the last one.", flush=True)
        sys.exit(1)
    subprocess.run(["docker", "service", "scale", f"inference_worker={current - 1}"], check=True)
    print(f"Scaled down to {current - 1} workers. Master marks dead in ~15s. Watch Grafana.", flush=True)


def slow_worker(worker_id: str, delay_ms: int):
    print(f"Adding {delay_ms}ms delay to {worker_id}...", flush=True)
    cid = _find_container(worker_id)
    if not cid:
        print(f"Container for {worker_id} not found.", flush=True)
        sys.exit(1)
    subprocess.run([
        "docker", "exec", "--privileged", cid,
        "sh", "-c",
        f"tc qdisc del dev eth0 root 2>/dev/null || true && "
        f"tc qdisc add dev eth0 root netem delay {delay_ms}ms"
    ], check=True)
    print(f"Network delay applied to {worker_id}.", flush=True)


def recover_worker(worker_id: str):
    """Scale back up — Swarm will create a new replica to replace the killed one."""
    print(f"Recovering {worker_id}...", flush=True)
    # Get current replica count and add 1
    result = subprocess.run(
        ["docker", "service", "ls", "--filter", "name=inference_worker", "--format", "{{.Replicas}}"],
        capture_output=True, text=True
    )
    replicas_str = result.stdout.strip()  # e.g. "3/4" or "3/3"
    current = int(replicas_str.split("/")[-1]) if replicas_str else 4
    subprocess.run(["docker", "service", "scale", f"inference_worker={current + 1}"], check=True)
    print(f"Scaled inference_worker to {current + 1}. New worker will register in ~10s.", flush=True)
    print("Circuit breaker transitions OPEN → HALF_OPEN after 30s cooldown.", flush=True)


def scale(count: int):
    subprocess.run(["docker", "service", "scale", f"inference_worker={count}"], check=True)
    print(f"Scaled to {count} workers.", flush=True)


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
    except Exception as e:
        print(f"Error reaching master: {e}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Chaos testing for inference system")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--kill", metavar="WORKER_ID", help="Kill a worker by its worker_id (e.g. worker-2)")
    group.add_argument("--slow", nargs=2, metavar=("WORKER_ID", "DELAY_MS"), help="Add network delay")
    group.add_argument("--recover", metavar="WORKER_ID", help="Scale up to replace a killed worker")
    group.add_argument("--scale", metavar="N", type=int, help="Set exact worker replica count")
    group.add_argument("--status", action="store_true", help="Show all worker statuses")
    args = parser.parse_args()

    if args.kill:
        kill_worker(args.kill)
    elif args.slow:
        slow_worker(args.slow[0], int(args.slow[1]))
    elif args.recover:
        recover_worker(args.recover)
    elif args.scale is not None:
        scale(args.scale)
    elif args.status:
        status()
