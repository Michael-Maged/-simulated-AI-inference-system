"""
Generate graphs from Locust CSV output.

Usage:
  # Single test overview
  python client/plot_results.py --csv client/results/peak_1000

  # Strategy comparison (run after all 3 strategy tests)
  python client/plot_results.py --compare-strategies \
      --rr   client/results/round_robin \
      --lc   client/results/least_connections \
      --la   client/results/load_aware

  # Scaling curve (run after tests at each user count)
  python client/plot_results.py --scaling \
      client/results/scale_100 \
      client/results/scale_500 \
      client/results/scale_1000 \
      client/results/scale_1500
"""
import argparse
import os
import sys
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

OUT_DIR = "client/results"


# ── helpers ──────────────────────────────────────────────────────────────────

def load_history(csv_prefix: str) -> pd.DataFrame:
    path = f"{csv_prefix}_stats_history.csv"
    if not os.path.exists(path):
        print(f"Not found: {path}")
        sys.exit(1)
    df = pd.read_csv(path)
    df = df[df["Name"] == "Aggregated"].copy()
    df["Timestamp"] = df["Timestamp"] - df["Timestamp"].min()
    return df


def load_stats(csv_prefix: str) -> dict:
    path = f"{csv_prefix}_stats.csv"
    if not os.path.exists(path):
        print(f"Not found: {path}")
        sys.exit(1)
    df = pd.read_csv(path)
    row = df[df["Name"] == "Aggregated"].iloc[0]
    return {
        "rps":         float(row["Requests/s"]),
        "failures_s":  float(row["Failures/s"]),
        "p50":         float(row["50%"]),
        "p95":         float(row["95%"]),
        "p99":         float(row["99%"]),
        "avg":         float(row["Average (ms)"]),
        "max":         float(row["Max (ms)"]),
        "total":       int(row["Request Count"]),
        "failures":    int(row["Failure Count"]),
    }


# ── single test overview ──────────────────────────────────────────────────────

def plot_overview(csv_prefix: str, out_dir: str):
    df = load_history(csv_prefix)
    stats = load_stats(csv_prefix)
    name = os.path.basename(csv_prefix)

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(f"Load Test — {name}\n"
                 f"RPS: {stats['rps']:.1f}  |  p95: {stats['p95']:.0f}ms  |  "
                 f"p99: {stats['p99']:.0f}ms  |  Failures: {stats['failures']}",
                 fontsize=12)

    axes[0, 0].plot(df["Timestamp"], df["Requests/s"], color="steelblue")
    axes[0, 0].set_title("Throughput (req/s)")
    axes[0, 0].set_xlabel("Time (s)")
    axes[0, 0].set_ylabel("req/s")
    axes[0, 0].grid(True, alpha=0.3)

    axes[0, 1].plot(df["Timestamp"], df["50%"],  label="p50", color="green")
    axes[0, 1].plot(df["Timestamp"], df["95%"],  label="p95", color="orange")
    axes[0, 1].plot(df["Timestamp"], df["99%"],  label="p99", color="red")
    axes[0, 1].set_title("Latency Percentiles (ms)")
    axes[0, 1].set_xlabel("Time (s)")
    axes[0, 1].set_ylabel("ms")
    axes[0, 1].legend()
    axes[0, 1].grid(True, alpha=0.3)

    axes[1, 0].plot(df["Timestamp"], df["User count"], color="purple")
    axes[1, 0].set_title("Concurrent Users")
    axes[1, 0].set_xlabel("Time (s)")
    axes[1, 0].grid(True, alpha=0.3)

    axes[1, 1].plot(df["Timestamp"], df["Failures/s"], color="red")
    axes[1, 1].set_title("Failure Rate (failures/s)")
    axes[1, 1].set_xlabel("Time (s)")
    axes[1, 1].grid(True, alpha=0.3)

    plt.tight_layout()
    out = os.path.join(out_dir, f"{name}_overview.png")
    plt.savefig(out, dpi=150)
    print(f"Saved: {out}")
    plt.close()


# ── strategy comparison ───────────────────────────────────────────────────────

def plot_strategy_comparison(prefixes: dict, out_dir: str):
    """prefixes = {"Round Robin": "path", "Least Connections": "path", "Load-Aware": "path"}"""
    labels = list(prefixes.keys())
    stats  = {label: load_stats(prefix) for label, prefix in prefixes.items()}

    fig, axes = plt.subplots(1, 3, figsize=(16, 6))
    fig.suptitle("Load Balancing Strategy Comparison", fontsize=14)
    colors = ["steelblue", "orange", "green"]

    # p95 latency bar chart
    p95 = [stats[l]["p95"] for l in labels]
    bars = axes[0].bar(labels, p95, color=colors)
    axes[0].bar_label(bars, fmt="%.0f ms", padding=3)
    axes[0].set_title("p95 Latency (ms)")
    axes[0].set_ylabel("ms")
    axes[0].set_ylim(0, max(p95) * 1.25)

    # RPS bar chart
    rps = [stats[l]["rps"] for l in labels]
    bars = axes[1].bar(labels, rps, color=colors)
    axes[1].bar_label(bars, fmt="%.1f", padding=3)
    axes[1].set_title("Throughput (req/s)")
    axes[1].set_ylabel("req/s")
    axes[1].set_ylim(0, max(rps) * 1.25)

    # Latency breakdown (p50 / p95 / p99) grouped bar
    x = range(len(labels))
    w = 0.25
    for i, (pct, col) in enumerate([("p50", "green"), ("p95", "orange"), ("p99", "red")]):
        vals = [stats[l][pct] for l in labels]
        axes[2].bar([xi + i*w for xi in x], vals, w, label=pct, color=col)
    axes[2].set_title("Latency Breakdown (ms)")
    axes[2].set_xticks([xi + w for xi in x])
    axes[2].set_xticklabels(labels)
    axes[2].set_ylabel("ms")
    axes[2].legend()

    plt.tight_layout()
    out = os.path.join(out_dir, "strategy_comparison.png")
    plt.savefig(out, dpi=150)
    print(f"Saved: {out}")
    plt.close()

    # Also print a table
    print(f"\n{'Strategy':<22} {'RPS':>8} {'p50 ms':>8} {'p95 ms':>8} {'p99 ms':>8} {'Failures':>10}")
    print("-" * 66)
    for l in labels:
        s = stats[l]
        print(f"{l:<22} {s['rps']:>8.1f} {s['p50']:>8.0f} {s['p95']:>8.0f} {s['p99']:>8.0f} {s['failures']:>10}")


# ── scaling curve ─────────────────────────────────────────────────────────────

def plot_scaling_curve(prefixes: list, out_dir: str):
    """prefixes = list of csv prefix paths, one per user-count test."""
    rows = []
    for prefix in prefixes:
        df = load_history(prefix)
        s  = load_stats(prefix)
        max_users = int(df["User count"].max())
        rows.append({
            "users": max_users,
            "rps":   s["rps"],
            "p50":   s["p50"],
            "p95":   s["p95"],
            "p99":   s["p99"],
        })
    rows.sort(key=lambda r: r["users"])

    users = [r["users"] for r in rows]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    fig.suptitle("Scaling Curve", fontsize=14)

    ax1.plot(users, [r["p50"] for r in rows], marker="o", label="p50", color="green")
    ax1.plot(users, [r["p95"] for r in rows], marker="o", label="p95", color="orange")
    ax1.plot(users, [r["p99"] for r in rows], marker="o", label="p99", color="red")
    ax1.set_title("Latency vs Concurrent Users")
    ax1.set_xlabel("Concurrent Users")
    ax1.set_ylabel("Latency (ms)")
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_locator(ticker.FixedLocator(users))

    ax2.plot(users, [r["rps"] for r in rows], marker="o", color="steelblue")
    ax2.set_title("Throughput vs Concurrent Users")
    ax2.set_xlabel("Concurrent Users")
    ax2.set_ylabel("req/s")
    ax2.grid(True, alpha=0.3)
    ax2.xaxis.set_major_locator(ticker.FixedLocator(users))

    plt.tight_layout()
    out = os.path.join(out_dir, "scaling_curve.png")
    plt.savefig(out, dpi=150)
    print(f"Saved: {out}")
    plt.close()

    print(f"\n{'Users':>8} {'RPS':>8} {'p50 ms':>8} {'p95 ms':>8} {'p99 ms':>8}")
    print("-" * 44)
    for r in rows:
        print(f"{r['users']:>8} {r['rps']:>8.1f} {r['p50']:>8.0f} {r['p95']:>8.0f} {r['p99']:>8.0f}")


# ── main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate graphs from Locust CSV output")
    parser.add_argument("--csv",    metavar="PREFIX", help="Single test overview")
    parser.add_argument("--out",    default=OUT_DIR,  help="Output directory")
    parser.add_argument("--compare-strategies", action="store_true")
    parser.add_argument("--rr",  metavar="PREFIX", help="Round Robin CSV prefix")
    parser.add_argument("--lc",  metavar="PREFIX", help="Least Connections CSV prefix")
    parser.add_argument("--la",  metavar="PREFIX", help="Load-Aware CSV prefix")
    parser.add_argument("--scaling", nargs="+", metavar="PREFIX",
                        help="List of CSV prefixes for scaling curve (one per user count)")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)

    if args.csv:
        plot_overview(args.csv, args.out)

    if args.compare_strategies:
        if not (args.rr and args.lc and args.la):
            print("--compare-strategies requires --rr --lc --la")
            sys.exit(1)
        plot_strategy_comparison({
            "Round Robin":       args.rr,
            "Least Connections": args.lc,
            "Load-Aware":        args.la,
        }, args.out)

    if args.scaling:
        plot_scaling_curve(args.scaling, args.out)

    if not any([args.csv, args.compare_strategies, args.scaling]):
        parser.print_help()
