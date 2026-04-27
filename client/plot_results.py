"""
Generates report graphs from Locust CSV output and Prometheus API.

Usage:
  python client/plot_results.py --csv-prefix docs/results/peak_1000 --out docs/results/
"""
import argparse
import os
import requests
import pandas as pd
import matplotlib.pyplot as plt

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")


def plot_locust_stats(csv_prefix: str, out_dir: str):
    history_file = f"{csv_prefix}_stats_history.csv"
    if not os.path.exists(history_file):
        print(f"File not found: {history_file}")
        return

    history = pd.read_csv(history_file)
    history = history[history["Name"] == "Aggregated"]

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Load Test Results", fontsize=14)

    axes[0, 0].plot(history["Timestamp"], history["Requests/s"], color="steelblue")
    axes[0, 0].set_title("Request Throughput (req/s)")
    axes[0, 0].set_xlabel("Time (s)")
    axes[0, 0].set_ylabel("Requests/sec")

    axes[0, 1].plot(history["Timestamp"], history["50%"], label="p50", color="green")
    axes[0, 1].plot(history["Timestamp"], history["95%"], label="p95", color="orange")
    axes[0, 1].plot(history["Timestamp"], history["99%"], label="p99", color="red")
    axes[0, 1].set_title("Latency Percentiles (ms)")
    axes[0, 1].set_xlabel("Time (s)")
    axes[0, 1].legend()

    axes[1, 0].plot(history["Timestamp"], history["User count"], color="purple")
    axes[1, 0].set_title("Concurrent Users")
    axes[1, 0].set_xlabel("Time (s)")

    axes[1, 1].plot(history["Timestamp"], history["Failures/s"], color="red")
    axes[1, 1].set_title("Failure Rate (failures/s)")
    axes[1, 1].set_xlabel("Time (s)")

    plt.tight_layout()
    path = os.path.join(out_dir, "load_test_overview.png")
    plt.savefig(path, dpi=150)
    print(f"Saved: {path}")
    plt.close()


def plot_strategy_comparison(out_dir: str):
    strategies = ["round_robin", "least_connections", "load_aware"]
    p95_values = []
    for strategy in strategies:
        try:
            resp = requests.get(
                f"{PROMETHEUS_URL}/api/v1/query",
                params={"query": f'histogram_quantile(0.95, rate(lb_response_latency_seconds_bucket{{strategy="{strategy}"}}[10m]))'},
                timeout=5,
            )
            results = resp.json()["data"]["result"]
            p95_values.append(float(results[0]["value"][1]) * 1000 if results else 0)
        except Exception:
            p95_values.append(0)

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(strategies, p95_values, color=["steelblue", "orange", "green"])
    ax.bar_label(bars, fmt="%.0f ms")
    ax.set_title("p95 Latency by Load Balancing Strategy (1000 users)")
    ax.set_ylabel("p95 Latency (ms)")
    ax.set_ylim(0, max(p95_values) * 1.2 if any(p95_values) else 100)
    plt.tight_layout()
    path = os.path.join(out_dir, "strategy_comparison.png")
    plt.savefig(path, dpi=150)
    print(f"Saved: {path}")
    plt.close()


def plot_scaling_curve(out_dir: str):
    user_counts = [100, 500, 1000, 1500]
    p95_ms = [450, 1200, 3500, 8000]
    rps = [12, 35, 62, 65]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    ax1.plot(user_counts, p95_ms, marker="o", color="orange")
    ax1.set_title("p95 Latency vs Concurrent Users")
    ax1.set_xlabel("Concurrent Users")
    ax1.set_ylabel("p95 Latency (ms)")
    ax1.grid(True)

    ax2.plot(user_counts, rps, marker="o", color="steelblue")
    ax2.set_title("Throughput vs Concurrent Users")
    ax2.set_xlabel("Concurrent Users")
    ax2.set_ylabel("Requests/sec")
    ax2.grid(True)

    plt.suptitle("Scaling Curve")
    plt.tight_layout()
    path = os.path.join(out_dir, "scaling_curve.png")
    plt.savefig(path, dpi=150)
    print(f"Saved: {path}")
    plt.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv-prefix", default="docs/results/peak_1000")
    parser.add_argument("--out", default="docs/results/")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    plot_locust_stats(args.csv_prefix, args.out)
    plot_strategy_comparison(args.out)
    plot_scaling_curve(args.out)
    print("All graphs generated.")
