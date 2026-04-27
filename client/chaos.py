"""
Chaos testing script. Run while Locust is active.

Usage:
  python client/chaos.py --kill worker-2
  python client/chaos.py --slow worker-3 500
  python client/chaos.py --recover worker-2
  python client/chaos.py --status
"""
import argparse
import subprocess
import sys
import time


def kill_worker(name: str):
    print(f"Killing {name}...", flush=True)
    result = subprocess.run(["docker", "compose", "stop", name], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"{name} stopped. Watch Grafana for recovery.", flush=True)
    else:
        print(f"Error: {result.stderr}", flush=True)
        sys.exit(1)


def slow_worker(name: str, delay_ms: int):
    print(f"Adding {delay_ms}ms network delay to {name}...", flush=True)
    container_id = subprocess.check_output(
        ["docker", "compose", "ps", "-q", name], text=True
    ).strip()
    if not container_id:
        print(f"Container {name} not found.", flush=True)
        sys.exit(1)
    subprocess.run([
        "docker", "exec", "--privileged", container_id,
        "sh", "-c",
        f"apt-get install -qq iproute2 2>/dev/null; "
        f"tc qdisc add dev eth0 root netem delay {delay_ms}ms"
    ], check=True)
    print(f"Network delay applied to {name}.", flush=True)


def recover_worker(name: str):
    print(f"Recovering {name}...", flush=True)
    subprocess.run(["docker", "compose", "start", name], check=True)
    print(f"{name} restarted. Circuit breaker will transition to HALF_OPEN in 30s.", flush=True)


def status():
    import httpx
    try:
        resp = httpx.get("http://localhost:8001/workers", timeout=5.0)
        workers = resp.json()
        print(f"{'Worker':<15} {'Alive':<8} {'Circuit':<12} {'Queue':<8} {'p95 ms'}")
        print("-" * 55)
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
    group.add_argument("--kill", metavar="WORKER", help="Stop a worker container")
    group.add_argument("--slow", nargs=2, metavar=("WORKER", "DELAY_MS"), help="Add network delay")
    group.add_argument("--recover", metavar="WORKER", help="Restart a stopped worker")
    group.add_argument("--status", action="store_true", help="Show worker status")
    args = parser.parse_args()

    if args.kill:
        kill_worker(args.kill)
    elif args.slow:
        slow_worker(args.slow[0], int(args.slow[1]))
    elif args.recover:
        recover_worker(args.recover)
    elif args.status:
        status()
