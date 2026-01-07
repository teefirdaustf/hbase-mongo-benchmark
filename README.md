# HBase vs MongoDB Benchmark

A benchmarking suite to compare query performance between Apache HBase and MongoDB using Docker containers. Measure latency, throughput, and scalability metrics with your own dataset.

## Overview

This project provides a complete environment for benchmarking two popular NoSQL databases:

| Database | Type | Best For |
|----------|------|----------|
| **MongoDB** | Document Store | Flexible schemas, rich queries, aggregations |
| **HBase** | Wide-Column Store | Sequential reads/writes, time-series, massive scale |

## Prerequisites

- **Docker** & **Docker Compose** (v2.0+)
- **Python 3.9+**
- **~4GB RAM** available for containers

## Project Structure

```
hbase-mongo-benchmark/
├── docker-compose.yml          # Container orchestration
├── hbase/
│   ├── Dockerfile              # Custom HBase image
│   ├── entrypoint.sh           # Startup script
│   └── hbase-site.xml          # HBase configuration
├── scripts/
│   ├── requirements.txt        # Python dependencies
│   ├── import_to_mongodb.py    # Load data into MongoDB
│   ├── import_to_hbase.py      # Load data into HBase
│   ├── benchmark.py            # Run performance tests
│   └── analyze_results.py      # Generate reports & charts
├── data/                       # Place your parquet files here
└── results/                    # Benchmark output files
```

## Quick Start

### 1. Clone and Setup

```bash
cd hbase-mongo-benchmark

# Install Python dependencies
pip3 install -r scripts/requirements.txt
```

### 2. Add Your Data

Place your parquet files in the `data/` directory:

```bash
cp /path/to/your/*.parquet data/
```

### 3. Start Databases

```bash
# Build and start containers
docker-compose up -d --build

# Wait for services to be ready (HBase takes ~60-90 seconds)
docker-compose ps

# Check HBase is ready
docker-compose logs hbase | grep "HBase is ready"
```

### 4. Import Data

```bash
# Import to MongoDB
python3 scripts/import_to_mongodb.py

# Import to HBase
python3 scripts/import_to_hbase.py
```

### 5. Run Benchmarks

```bash
python3 scripts/benchmark.py
```

### 6. Analyze Results

```bash
python3 scripts/analyze_results.py
```

## Detailed Usage

### Starting the Environment

```bash
# Start all services
docker-compose up -d --build

# Start only MongoDB
docker-compose up -d mongodb

# Start only HBase
docker-compose up -d hbase

# View logs
docker-compose logs -f

# Stop all services
docker-compose down

# Stop and remove volumes (clean slate)
docker-compose down -v
```

### Web UIs

| Service | URL | Description |
|---------|-----|-------------|
| HBase Master | http://localhost:16010 | Cluster status, tables, regions |
| HBase RegionServer | http://localhost:16030 | RegionServer metrics |

### Import Scripts

Both import scripts support environment variables for configuration:

```bash
# MongoDB import options
MONGODB_HOST=localhost \
MONGODB_PORT=27017 \
MONGODB_DB=benchmark \
MONGODB_COLLECTION=data \
DATA_DIR=./data \
BATCH_SIZE=5000 \
python3 scripts/import_to_mongodb.py

# HBase import options
HBASE_HOST=localhost \
HBASE_THRIFT_PORT=9090 \
HBASE_TABLE=benchmark \
HBASE_CF=cf \
DATA_DIR=./data \
BATCH_SIZE=5000 \
python3 scripts/import_to_hbase.py
```

### Benchmark Configuration

Customize benchmark parameters:

```bash
NUM_ITERATIONS=100 \
WARMUP_ITERATIONS=10 \
RESULTS_DIR=./results \
python3 scripts/benchmark.py
```

## Understanding the Results

### Output Files

After running benchmarks, you'll find these files in `results/`:

| File | Description |
|------|-------------|
| `benchmark_YYYYMMDD_HHMMSS.json` | Raw benchmark data |
| `latency_comparison_*.png` | Latency percentile charts |
| `throughput_comparison_*.png` | Operations/second charts |
| `summary_*.md` | Markdown report |

### Benchmark Tests

| Test | Description | What It Measures |
|------|-------------|------------------|
| **Point Query** | Single row lookup by key | Random access performance |
| **Range Scan (100)** | Fetch 100 sequential rows | Small scan performance |
| **Range Scan (1000)** | Fetch 1000 sequential rows | Large scan performance |
| **Count All** | Count total rows | Full table scan speed |
| **Aggregation/Prefix** | MongoDB aggregation / HBase prefix scan | Analytical query performance |

### Metrics Explained

#### Latency Metrics (lower is better)

| Metric | Description |
|--------|-------------|
| **p50 (median)** | 50% of requests complete within this time |
| **p95** | 95% of requests complete within this time |
| **p99** | 99% of requests complete within this time (tail latency) |
| **Mean** | Average response time |
| **Min/Max** | Best and worst case latency |

#### Throughput (higher is better)

| Metric | Description |
|--------|-------------|
| **ops/sec** | Operations completed per second |

### Interpreting Results

#### Example Output

```
POINT QUERY
--------------------------------------------------------------------------------
Database         p50       p95       p99      Mean      Throughput
                (ms)      (ms)      (ms)      (ms)       (ops/sec)
--------------------------------------------------------------------------------
MongoDB        0.234     0.456     0.891     0.267         3745.32
HBase          0.512     1.234     2.456     0.634         1578.45
```

#### What to Look For

1. **p50 vs p99 Gap**: A large gap indicates inconsistent performance
   - MongoDB p50=0.2ms, p99=0.9ms → 4.5x difference (good)
   - HBase p50=0.5ms, p99=2.5ms → 5x difference (acceptable)

2. **Throughput Scaling**: Higher ops/sec = better for high-traffic workloads

3. **Test-Specific Performance**:
   - **Point queries**: Tests random access - important for key-value lookups
   - **Range scans**: Tests sequential access - important for analytics
   - **Count/Aggregation**: Tests full-table operations - important for reporting

### When to Choose Each Database

| Choose MongoDB When | Choose HBase When |
|---------------------|-------------------|
| Complex queries with filters | Simple key-based access patterns |
| Flexible, evolving schemas | Fixed, wide-column schemas |
| Rich aggregation pipelines | Sequential/time-series writes |
| Moderate scale (millions of docs) | Massive scale (billions of rows) |
| Developer productivity priority | Raw throughput priority |

## Troubleshooting

### HBase Won't Start

```bash
# Check logs
docker-compose logs hbase

# Restart with fresh data
docker-compose down -v
docker-compose up -d --build
```

### Connection Refused (HBase)

HBase takes 60-90 seconds to fully start. Wait for:
```bash
docker-compose logs hbase | grep "Thrift server is ready"
```

### Import Fails

```bash
# Verify databases are running
docker-compose ps

# Test MongoDB connection
docker exec -it benchmark-mongodb mongosh --eval "db.adminCommand('ping')"

# Test HBase connection (Thrift port)
nc -zv localhost 9090
```

### Out of Memory

Reduce container memory limits in `docker-compose.yml`:
```yaml
deploy:
  resources:
    limits:
      memory: 1G  # Reduce from 2G
```

## Advanced Configuration

### HBase Tuning (`hbase/hbase-site.xml`)

```xml
<!-- Increase handler threads for more concurrent requests -->
<property>
  <name>hbase.regionserver.handler.count</name>
  <value>50</value>
</property>

<!-- Increase memstore size for write-heavy workloads -->
<property>
  <name>hbase.hregion.memstore.flush.size</name>
  <value>268435456</value> <!-- 256MB -->
</property>
```

### MongoDB Tuning

Add to `docker-compose.yml` under mongodb service:
```yaml
command: ["--wiredTigerCacheSizeGB", "1"]
```

## License

MIT
