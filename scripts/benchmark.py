#!/usr/bin/env python3
"""
Benchmark script for comparing MongoDB and HBase query performance.
"""

import os
import sys
import json
import time
import random
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from dataclasses import dataclass, asdict

import pandas as pd
import numpy as np
from pymongo import MongoClient
import happybase
from tqdm import tqdm


# Configuration
MONGODB_HOST = os.getenv("MONGODB_HOST", "localhost")
MONGODB_PORT = int(os.getenv("MONGODB_PORT", 27017))
MONGODB_DB = os.getenv("MONGODB_DB", "benchmark")
MONGODB_COLLECTION = os.getenv("MONGODB_COLLECTION", "data")

HBASE_HOST = os.getenv("HBASE_HOST", "localhost")
HBASE_THRIFT_PORT = int(os.getenv("HBASE_THRIFT_PORT", 9090))
HBASE_TABLE = os.getenv("HBASE_TABLE", "benchmark")
HBASE_CF = os.getenv("HBASE_CF", "cf")

RESULTS_DIR = os.getenv("RESULTS_DIR", "./results")
NUM_ITERATIONS = int(os.getenv("NUM_ITERATIONS", 100))
WARMUP_ITERATIONS = int(os.getenv("WARMUP_ITERATIONS", 10))


@dataclass
class BenchmarkResult:
    """Results from a single benchmark test."""
    test_name: str
    database: str
    iterations: int
    latencies_ms: list[float]

    @property
    def p50(self) -> float:
        return np.percentile(self.latencies_ms, 50)

    @property
    def p95(self) -> float:
        return np.percentile(self.latencies_ms, 95)

    @property
    def p99(self) -> float:
        return np.percentile(self.latencies_ms, 99)

    @property
    def mean(self) -> float:
        return statistics.mean(self.latencies_ms)

    @property
    def std(self) -> float:
        return statistics.stdev(self.latencies_ms) if len(self.latencies_ms) > 1 else 0

    @property
    def min_latency(self) -> float:
        return min(self.latencies_ms)

    @property
    def max_latency(self) -> float:
        return max(self.latencies_ms)

    @property
    def throughput(self) -> float:
        """Operations per second."""
        total_time = sum(self.latencies_ms) / 1000  # Convert to seconds
        return self.iterations / total_time if total_time > 0 else 0

    def to_dict(self) -> dict:
        return {
            "test_name": self.test_name,
            "database": self.database,
            "iterations": self.iterations,
            "p50_ms": round(self.p50, 3),
            "p95_ms": round(self.p95, 3),
            "p99_ms": round(self.p99, 3),
            "mean_ms": round(self.mean, 3),
            "std_ms": round(self.std, 3),
            "min_ms": round(self.min_latency, 3),
            "max_ms": round(self.max_latency, 3),
            "throughput_ops": round(self.throughput, 2)
        }


class MongoDBBenchmark:
    """MongoDB benchmark implementation."""

    def __init__(self):
        self.client = MongoClient(MONGODB_HOST, MONGODB_PORT)
        self.db = self.client[MONGODB_DB]
        self.collection = self.db[MONGODB_COLLECTION]
        self.sample_keys = []
        self._load_sample_keys()

    def _load_sample_keys(self):
        """Load sample document IDs for testing."""
        # Get first column name (key field)
        sample = self.collection.find_one()
        if sample:
            self.key_field = "_id"
            # Get random sample of keys
            pipeline = [{"$sample": {"size": NUM_ITERATIONS * 2}}]
            docs = list(self.collection.aggregate(pipeline))
            self.sample_keys = [doc["_id"] for doc in docs]

            # Also get other field names for queries
            self.fields = [k for k in sample.keys() if k != "_id"]

    def close(self):
        self.client.close()

    def point_query(self, key) -> dict:
        """Single document lookup by _id."""
        return self.collection.find_one({"_id": key})

    def range_scan(self, limit: int = 100) -> list:
        """Scan a range of documents."""
        return list(self.collection.find().limit(limit))

    def filtered_query(self, field: str, value: Any) -> list:
        """Query with filter on a field."""
        return list(self.collection.find({field: value}).limit(100))

    def count_query(self) -> int:
        """Count all documents."""
        return self.collection.count_documents({})

    def aggregation_query(self, field: str) -> list:
        """Simple aggregation - count by field value."""
        pipeline = [
            {"$group": {"_id": f"${field}", "count": {"$sum": 1}}},
            {"$limit": 100}
        ]
        return list(self.collection.aggregate(pipeline))


class HBaseBenchmark:
    """HBase benchmark implementation."""

    def __init__(self):
        self.connection = happybase.Connection(HBASE_HOST, port=HBASE_THRIFT_PORT)
        self.connection.open()
        self.table = self.connection.table(HBASE_TABLE)
        self.cf = HBASE_CF
        self.sample_keys = []
        self._load_sample_keys()

    def _load_sample_keys(self):
        """Load sample row keys for testing."""
        # Scan to get sample keys
        keys = []
        for key, _ in self.table.scan(limit=NUM_ITERATIONS * 2):
            keys.append(key)
        self.sample_keys = keys

        # Get column names
        if keys:
            row = self.table.row(keys[0])
            self.columns = [col.decode().split(":")[1] for col in row.keys()]

    def close(self):
        self.connection.close()

    def point_query(self, key: bytes) -> dict:
        """Single row lookup by key."""
        return self.table.row(key)

    def range_scan(self, limit: int = 100) -> list:
        """Scan a range of rows."""
        return list(self.table.scan(limit=limit))

    def filtered_scan(self, column: str, value: str, limit: int = 100) -> list:
        """Scan with SingleColumnValueFilter."""
        col_filter = f"SingleColumnValueFilter('{self.cf}', '{column}', =, 'binary:{value}')"
        return list(self.table.scan(filter=col_filter, limit=limit))

    def count_scan(self) -> int:
        """Count all rows (full table scan)."""
        count = 0
        for _ in self.table.scan():
            count += 1
        return count

    def prefix_scan(self, prefix: bytes, limit: int = 100) -> list:
        """Scan rows with a key prefix."""
        return list(self.table.scan(row_prefix=prefix, limit=limit))


def run_benchmark(name: str, database: str, func: Callable, iterations: int = NUM_ITERATIONS) -> BenchmarkResult:
    """Run a benchmark test and collect timing data."""
    latencies = []

    # Warmup
    for _ in range(WARMUP_ITERATIONS):
        func()

    # Actual benchmark
    for _ in tqdm(range(iterations), desc=f"  {database}", leave=False):
        start = time.perf_counter()
        func()
        end = time.perf_counter()
        latencies.append((end - start) * 1000)  # Convert to ms

    return BenchmarkResult(
        test_name=name,
        database=database,
        iterations=iterations,
        latencies_ms=latencies
    )


def run_all_benchmarks() -> list[BenchmarkResult]:
    """Run all benchmark tests."""
    results = []

    print("\nConnecting to databases...")
    try:
        mongo = MongoDBBenchmark()
        print(f"  MongoDB: Connected ({len(mongo.sample_keys)} sample keys)")
    except Exception as e:
        print(f"  MongoDB: Failed to connect - {e}")
        mongo = None

    try:
        hbase = HBaseBenchmark()
        print(f"  HBase: Connected ({len(hbase.sample_keys)} sample keys)")
    except Exception as e:
        print(f"  HBase: Failed to connect - {e}")
        hbase = None

    if not mongo and not hbase:
        print("No databases available for benchmarking!")
        sys.exit(1)

    # Test 1: Point Queries
    print("\n[1/5] Point Query (single row lookup)")
    if mongo and mongo.sample_keys:
        keys = random.sample(mongo.sample_keys, min(NUM_ITERATIONS, len(mongo.sample_keys)))
        key_iter = iter(keys)
        results.append(run_benchmark(
            "point_query", "MongoDB",
            lambda: mongo.point_query(next(key_iter, keys[0]))
        ))

    if hbase and hbase.sample_keys:
        keys = random.sample(hbase.sample_keys, min(NUM_ITERATIONS, len(hbase.sample_keys)))
        key_iter = iter(keys)
        results.append(run_benchmark(
            "point_query", "HBase",
            lambda: hbase.point_query(next(key_iter, keys[0]))
        ))

    # Test 2: Range Scan
    print("\n[2/5] Range Scan (100 rows)")
    if mongo:
        results.append(run_benchmark(
            "range_scan_100", "MongoDB",
            lambda: mongo.range_scan(100)
        ))

    if hbase:
        results.append(run_benchmark(
            "range_scan_100", "HBase",
            lambda: hbase.range_scan(100)
        ))

    # Test 3: Large Range Scan
    print("\n[3/5] Large Range Scan (1000 rows)")
    if mongo:
        results.append(run_benchmark(
            "range_scan_1000", "MongoDB",
            lambda: mongo.range_scan(1000),
            iterations=50  # Fewer iterations for large scans
        ))

    if hbase:
        results.append(run_benchmark(
            "range_scan_1000", "HBase",
            lambda: hbase.range_scan(1000),
            iterations=50
        ))

    # Test 4: Count Query
    print("\n[4/5] Count Query (full table)")
    if mongo:
        results.append(run_benchmark(
            "count_all", "MongoDB",
            lambda: mongo.count_query(),
            iterations=20  # Very few iterations - expensive operation
        ))

    if hbase:
        results.append(run_benchmark(
            "count_all", "HBase",
            lambda: hbase.count_scan(),
            iterations=5  # HBase requires full scan
        ))

    # Test 5: Aggregation (MongoDB) / Prefix Scan (HBase)
    print("\n[5/5] Aggregation / Prefix Scan")
    if mongo and mongo.fields:
        field = mongo.fields[0]
        results.append(run_benchmark(
            "aggregation", "MongoDB",
            lambda: mongo.aggregation_query(field),
            iterations=50
        ))

    if hbase and hbase.sample_keys:
        # Use first 2 chars as prefix
        prefix = hbase.sample_keys[0][:2] if hbase.sample_keys else b""
        results.append(run_benchmark(
            "prefix_scan", "HBase",
            lambda: hbase.prefix_scan(prefix, 100),
            iterations=50
        ))

    # Cleanup
    if mongo:
        mongo.close()
    if hbase:
        hbase.close()

    return results


def print_results(results: list[BenchmarkResult]):
    """Print benchmark results in a formatted table."""
    print("\n" + "=" * 80)
    print("BENCHMARK RESULTS")
    print("=" * 80)

    # Group by test name
    tests = {}
    for r in results:
        if r.test_name not in tests:
            tests[r.test_name] = {}
        tests[r.test_name][r.database] = r

    for test_name, dbs in tests.items():
        print(f"\n{test_name.upper().replace('_', ' ')}")
        print("-" * 80)
        print(f"{'Database':<12} {'p50':>10} {'p95':>10} {'p99':>10} {'Mean':>10} {'Throughput':>15}")
        print(f"{'':12} {'(ms)':>10} {'(ms)':>10} {'(ms)':>10} {'(ms)':>10} {'(ops/sec)':>15}")
        print("-" * 80)

        for db_name, result in dbs.items():
            print(f"{db_name:<12} {result.p50:>10.3f} {result.p95:>10.3f} {result.p99:>10.3f} "
                  f"{result.mean:>10.3f} {result.throughput:>15.2f}")


def save_results(results: list[BenchmarkResult]):
    """Save results to JSON and CSV files."""
    Path(RESULTS_DIR).mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_filename = f"{RESULTS_DIR}/benchmark_{timestamp}.json"
    csv_filename = f"{RESULTS_DIR}/benchmark_{timestamp}.csv"

    output = {
        "timestamp": timestamp,
        "config": {
            "num_iterations": NUM_ITERATIONS,
            "warmup_iterations": WARMUP_ITERATIONS,
            "mongodb_host": MONGODB_HOST,
            "hbase_host": HBASE_HOST
        },
        "results": [r.to_dict() for r in results]
    }

    # Save JSON
    with open(json_filename, "w") as f:
        json.dump(output, f, indent=2)

    # Save CSV
    results_df = pd.DataFrame([r.to_dict() for r in results])
    results_df.to_csv(csv_filename, index=False)

    print(f"\nResults saved to:")
    print(f"  JSON: {json_filename}")
    print(f"  CSV:  {csv_filename}")
    return json_filename, csv_filename


def main():
    print("=" * 80)
    print("HBase vs MongoDB Benchmark")
    print("=" * 80)
    print(f"\nConfiguration:")
    print(f"  Iterations: {NUM_ITERATIONS}")
    print(f"  Warmup: {WARMUP_ITERATIONS}")

    # Run benchmarks
    results = run_all_benchmarks()

    # Print results
    print_results(results)

    # Save results
    save_results(results)

    print("\n" + "=" * 80)
    print("Benchmark complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
