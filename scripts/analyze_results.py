#!/usr/bin/env python3
"""
Analyze benchmark results and generate comparison charts.
"""

import os
import sys
import json
import csv
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from tabulate import tabulate


RESULTS_DIR = os.getenv("RESULTS_DIR", "./results")


def load_latest_results() -> dict:
    """Load the most recent benchmark results file."""
    results_path = Path(RESULTS_DIR)
    json_files = list(results_path.glob("benchmark_*.json"))

    if not json_files:
        print(f"No benchmark results found in {RESULTS_DIR}")
        print("Run benchmark.py first to generate results.")
        sys.exit(1)

    # Sort by modification time, get latest
    latest = max(json_files, key=lambda f: f.stat().st_mtime)
    print(f"Loading results from: {latest.name}")

    with open(latest) as f:
        return json.load(f)


def load_specific_results(filename: str) -> dict:
    """Load a specific results file."""
    filepath = Path(RESULTS_DIR) / filename
    if not filepath.exists():
        print(f"Results file not found: {filepath}")
        sys.exit(1)

    with open(filepath) as f:
        return json.load(f)


def create_comparison_table(results: list[dict]) -> str:
    """Create a formatted comparison table."""
    # Group results by test
    tests = {}
    for r in results:
        test_name = r["test_name"]
        if test_name not in tests:
            tests[test_name] = {}
        tests[test_name][r["database"]] = r

    # Build table data
    headers = ["Test", "Metric", "MongoDB", "HBase", "Winner", "Diff %"]
    rows = []

    for test_name, dbs in tests.items():
        mongo = dbs.get("MongoDB", {})
        hbase = dbs.get("HBase", {})

        metrics = [
            ("p50_ms", "p50 (ms)"),
            ("p95_ms", "p95 (ms)"),
            ("p99_ms", "p99 (ms)"),
            ("mean_ms", "Mean (ms)"),
            ("throughput_ops", "Throughput (ops/s)")
        ]

        for metric_key, metric_name in metrics:
            mongo_val = mongo.get(metric_key, "N/A")
            hbase_val = hbase.get(metric_key, "N/A")

            # Determine winner (lower is better for latency, higher for throughput)
            winner = "—"
            diff_pct = "—"

            if isinstance(mongo_val, (int, float)) and isinstance(hbase_val, (int, float)):
                if metric_key == "throughput_ops":
                    # Higher is better
                    if mongo_val > hbase_val:
                        winner = "MongoDB"
                        diff_pct = f"+{((mongo_val - hbase_val) / hbase_val * 100):.1f}%"
                    elif hbase_val > mongo_val:
                        winner = "HBase"
                        diff_pct = f"+{((hbase_val - mongo_val) / mongo_val * 100):.1f}%"
                    else:
                        winner = "Tie"
                        diff_pct = "0%"
                else:
                    # Lower is better (latency)
                    if mongo_val < hbase_val:
                        winner = "MongoDB"
                        diff_pct = f"-{((hbase_val - mongo_val) / hbase_val * 100):.1f}%"
                    elif hbase_val < mongo_val:
                        winner = "HBase"
                        diff_pct = f"-{((mongo_val - hbase_val) / mongo_val * 100):.1f}%"
                    else:
                        winner = "Tie"
                        diff_pct = "0%"

            rows.append([
                test_name.replace("_", " ").title() if metric_key == "p50_ms" else "",
                metric_name,
                f"{mongo_val:.3f}" if isinstance(mongo_val, float) else str(mongo_val),
                f"{hbase_val:.3f}" if isinstance(hbase_val, float) else str(hbase_val),
                winner,
                diff_pct
            ])

        rows.append(["", "", "", "", "", ""])  # Spacer row

    return tabulate(rows[:-1], headers=headers, tablefmt="grid")


def create_latency_chart(results: list[dict], output_path: str):
    """Create a bar chart comparing latencies."""
    # Extract data
    tests = {}
    for r in results:
        test = r["test_name"]
        if test not in tests:
            tests[test] = {"MongoDB": {}, "HBase": {}}
        tests[test][r["database"]] = {
            "p50": r.get("p50_ms", 0),
            "p95": r.get("p95_ms", 0),
            "p99": r.get("p99_ms", 0)
        }

    # Create subplots
    fig, axes = plt.subplots(1, len(tests), figsize=(4 * len(tests), 6))
    if len(tests) == 1:
        axes = [axes]

    colors = {"MongoDB": "#4DB33D", "HBase": "#E31837"}
    bar_width = 0.35
    x = np.arange(3)  # p50, p95, p99

    for ax, (test_name, dbs) in zip(axes, tests.items()):
        for i, (db_name, latencies) in enumerate(dbs.items()):
            if latencies:
                values = [latencies["p50"], latencies["p95"], latencies["p99"]]
                offset = (i - 0.5) * bar_width
                ax.bar(x + offset, values, bar_width, label=db_name, color=colors.get(db_name, "gray"))

        ax.set_xlabel("Percentile")
        ax.set_ylabel("Latency (ms)")
        ax.set_title(test_name.replace("_", " ").title())
        ax.set_xticks(x)
        ax.set_xticklabels(["p50", "p95", "p99"])
        ax.legend()
        ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"Latency chart saved to: {output_path}")


def create_throughput_chart(results: list[dict], output_path: str):
    """Create a bar chart comparing throughput."""
    # Extract throughput data
    tests = []
    mongo_throughput = []
    hbase_throughput = []

    test_data = {}
    for r in results:
        test = r["test_name"]
        if test not in test_data:
            test_data[test] = {}
        test_data[test][r["database"]] = r.get("throughput_ops", 0)

    for test, dbs in test_data.items():
        tests.append(test.replace("_", "\n"))
        mongo_throughput.append(dbs.get("MongoDB", 0))
        hbase_throughput.append(dbs.get("HBase", 0))

    # Create chart
    fig, ax = plt.subplots(figsize=(10, 6))

    x = np.arange(len(tests))
    bar_width = 0.35

    ax.bar(x - bar_width/2, mongo_throughput, bar_width, label="MongoDB", color="#4DB33D")
    ax.bar(x + bar_width/2, hbase_throughput, bar_width, label="HBase", color="#E31837")

    ax.set_xlabel("Test")
    ax.set_ylabel("Throughput (ops/sec)")
    ax.set_title("Throughput Comparison: MongoDB vs HBase")
    ax.set_xticks(x)
    ax.set_xticklabels(tests)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    # Add value labels on bars
    for i, (m, h) in enumerate(zip(mongo_throughput, hbase_throughput)):
        if m > 0:
            ax.annotate(f"{m:.0f}", xy=(i - bar_width/2, m), ha="center", va="bottom", fontsize=8)
        if h > 0:
            ax.annotate(f"{h:.0f}", xy=(i + bar_width/2, h), ha="center", va="bottom", fontsize=8)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"Throughput chart saved to: {output_path}")


def save_comparison_csv(results: list[dict], output_path: str):
    """Save detailed comparison analysis to CSV."""
    rows = []

    # Group results by test
    tests = {}
    for r in results:
        test_name = r["test_name"]
        if test_name not in tests:
            tests[test_name] = {}
        tests[test_name][r["database"]] = r

    for test_name, dbs in tests.items():
        mongo = dbs.get("MongoDB", {})
        hbase = dbs.get("HBase", {})

        metrics = [
            ("p50_ms", "p50 (ms)"),
            ("p95_ms", "p95 (ms)"),
            ("p99_ms", "p99 (ms)"),
            ("mean_ms", "Mean (ms)"),
            ("std_ms", "Std Dev (ms)"),
            ("min_ms", "Min (ms)"),
            ("max_ms", "Max (ms)"),
            ("throughput_ops", "Throughput (ops/s)")
        ]

        for metric_key, metric_name in metrics:
            mongo_val = mongo.get(metric_key, None)
            hbase_val = hbase.get(metric_key, None)

            # Determine winner
            winner = ""
            diff_pct = ""

            if mongo_val is not None and hbase_val is not None:
                if metric_key == "throughput_ops":
                    # Higher is better
                    if mongo_val > hbase_val:
                        winner = "MongoDB"
                        diff_pct = ((mongo_val - hbase_val) / hbase_val * 100) if hbase_val != 0 else 0
                    elif hbase_val > mongo_val:
                        winner = "HBase"
                        diff_pct = ((hbase_val - mongo_val) / mongo_val * 100) if mongo_val != 0 else 0
                    else:
                        winner = "Tie"
                        diff_pct = 0
                else:
                    # Lower is better (latency)
                    if mongo_val < hbase_val:
                        winner = "MongoDB"
                        diff_pct = -((hbase_val - mongo_val) / hbase_val * 100) if hbase_val != 0 else 0
                    elif hbase_val < mongo_val:
                        winner = "HBase"
                        diff_pct = -((mongo_val - hbase_val) / mongo_val * 100) if mongo_val != 0 else 0
                    else:
                        winner = "Tie"
                        diff_pct = 0

            rows.append({
                "test_name": test_name,
                "metric": metric_name,
                "mongodb_value": mongo_val,
                "hbase_value": hbase_val,
                "winner": winner,
                "difference_pct": round(diff_pct, 2) if isinstance(diff_pct, float) else diff_pct
            })

    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False)
    print(f"Comparison CSV saved to: {output_path}")


def save_raw_results_csv(results: list[dict], output_path: str):
    """Save raw benchmark results to CSV."""
    df = pd.DataFrame(results)
    df.to_csv(output_path, index=False)
    print(f"Raw results CSV saved to: {output_path}")


def create_summary_report(data: dict, output_path: str):
    """Create a markdown summary report."""
    results = data["results"]
    config = data["config"]
    timestamp = data["timestamp"]

    # Count wins
    mongo_wins = 0
    hbase_wins = 0

    for r in results:
        # This is simplified - a real implementation would compare across tests
        pass

    report = f"""# Benchmark Results Summary

**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Data Timestamp:** {timestamp}

## Configuration

| Parameter | Value |
|-----------|-------|
| Iterations | {config.get('num_iterations', 'N/A')} |
| Warmup Iterations | {config.get('warmup_iterations', 'N/A')} |
| MongoDB Host | {config.get('mongodb_host', 'N/A')} |
| HBase Host | {config.get('hbase_host', 'N/A')} |

## Results

{create_comparison_table(results)}

## Key Findings

### Latency Analysis
- **Point Queries**: Compare single-row lookup performance
- **Range Scans**: Compare sequential read performance
- **Count Operations**: Full table scan comparison

### Throughput Analysis
- Operations per second for each test type
- Higher values indicate better performance

## Charts

- `latency_comparison.png`: Percentile latency comparison
- `throughput_comparison.png`: Operations per second comparison

## Notes

- MongoDB uses a document model with built-in indexing
- HBase uses a wide-column store with row-key based access
- Results may vary based on data distribution and query patterns
"""

    with open(output_path, "w") as f:
        f.write(report)

    print(f"Summary report saved to: {output_path}")


def main():
    print("=" * 60)
    print("Benchmark Results Analysis")
    print("=" * 60)

    # Check for command line argument (specific file)
    if len(sys.argv) > 1:
        data = load_specific_results(sys.argv[1])
    else:
        data = load_latest_results()

    results = data["results"]

    # Print comparison table
    print("\n" + create_comparison_table(results))

    # Create output directory
    Path(RESULTS_DIR).mkdir(parents=True, exist_ok=True)
    timestamp = data.get("timestamp", datetime.now().strftime("%Y%m%d_%H%M%S"))

    # Generate charts
    print("\nGenerating charts...")
    try:
        create_latency_chart(results, f"{RESULTS_DIR}/latency_comparison_{timestamp}.png")
        create_throughput_chart(results, f"{RESULTS_DIR}/throughput_comparison_{timestamp}.png")
    except Exception as e:
        print(f"Warning: Could not generate charts - {e}")
        print("Install matplotlib for chart generation: pip install matplotlib")

    # Generate summary report
    create_summary_report(data, f"{RESULTS_DIR}/summary_{timestamp}.md")

    # Generate CSV files
    print("\nGenerating CSV files...")
    save_raw_results_csv(results, f"{RESULTS_DIR}/results_raw_{timestamp}.csv")
    save_comparison_csv(results, f"{RESULTS_DIR}/results_comparison_{timestamp}.csv")

    print("\n" + "=" * 60)
    print("Analysis complete!")
    print("=" * 60)
    print(f"\nOutput files in {RESULTS_DIR}/:")
    print(f"  - results_raw_{timestamp}.csv        (raw benchmark data)")
    print(f"  - results_comparison_{timestamp}.csv (side-by-side comparison)")
    print(f"  - summary_{timestamp}.md             (markdown report)")
    print(f"  - latency_comparison_{timestamp}.png (latency chart)")
    print(f"  - throughput_comparison_{timestamp}.png (throughput chart)")


if __name__ == "__main__":
    main()
