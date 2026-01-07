# HBase vs MongoDB Benchmarking Plan

## Overview
Benchmark query latency, throughput, and performance metrics between HBase and MongoDB using a 200k row, 9 column dataset running on Docker.

## Data Source
User-provided parquet files (4 files) will be imported into both databases.

## Architecture

### Docker Services

#### MongoDB Stack
- **mongodb**: MongoDB 7.0 server
  - Port: 27017
  - Standalone mode (sufficient for benchmarking)

#### HBase Stack
- **zookeeper**: Apache ZooKeeper 3.8 (required by HBase)
  - Port: 2181
- **hbase**: Apache HBase 2.5 (standalone mode)
  - REST API Port: 8080
  - Thrift Port: 9090
  - Master UI: 16010
  - RegionServer UI: 16030

### Network
- Custom bridge network `benchmark-net` for inter-container communication

### Volumes
- Persistent volumes for data storage to ensure consistent benchmarks
- `mongodb_data`: MongoDB data persistence
- `hbase_data`: HBase/HDFS data persistence
- `zookeeper_data`: ZooKeeper data persistence

## Implementation Steps

### Step 1: Create Docker Compose File
Create `docker-compose.yml` with:
- MongoDB service
- ZooKeeper service
- HBase service (standalone mode with embedded HDFS)
- Shared network
- Persistent volumes
- Health checks for service readiness

### Step 2: Create HBase Configuration
Create `hbase/hbase-site.xml` with:
- Standalone mode configuration
- ZooKeeper quorum settings
- Data directory settings

### Step 3: Create Parquet Import Scripts
Create scripts to import user's parquet files into both databases:
- `scripts/import_to_mongodb.py`: Read parquet files and bulk insert into MongoDB
- `scripts/import_to_hbase.py`: Read parquet files and batch put into HBase via happybase (Thrift)

### Step 4: Create Benchmark Scripts
Create `scripts/benchmark.py` with tests for:
- **Point queries**: Single row lookups by key
- **Range queries**: Scan operations with filters
- **Aggregation queries**: Count, sum, average operations
- **Write operations**: Insert/update throughput
- **Bulk operations**: Batch read/write performance

### Step 5: Create Results Analysis
- `scripts/analyze_results.py`: Generate comparison charts and statistics

## File Structure
```
hbase-mongo-benchmark/
├── docker-compose.yml
├── hbase/
│   └── hbase-site.xml
├── scripts/
│   ├── requirements.txt
│   ├── import_to_mongodb.py
│   ├── import_to_hbase.py
│   ├── benchmark.py
│   └── analyze_results.py
├── data/
│   └── *.parquet (user-provided parquet files)
├── results/
│   └── (benchmark results)
└── plan.md
```

## Benchmark Metrics
1. **Latency**: p50, p95, p99 response times
2. **Throughput**: Operations per second
3. **Resource Usage**: CPU, memory consumption
4. **Scalability**: Performance under concurrent load

## Usage Instructions
```bash
# 1. Place parquet files in data/ directory
cp /path/to/your/*.parquet data/

# 2. Start services
docker-compose up -d

# 3. Wait for services to be healthy
docker-compose ps

# 4. Import parquet data into databases
python scripts/import_to_mongodb.py
python scripts/import_to_hbase.py

# 5. Run benchmarks
python scripts/benchmark.py

# 6. Analyze results
python scripts/analyze_results.py
```

## Notes
- HBase standalone mode is used for simplicity (no separate HDFS cluster)
- MongoDB runs without replica set for fair comparison
- Both databases will use similar resource limits for fair benchmarking
- Parquet files will be read using PyArrow/pandas and imported in batches
