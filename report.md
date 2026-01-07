# HBase vs MongoDB Benchmark Report

**Date:** January 7, 2026
**Dataset:** 200,000 records, 9 columns
**Environment:** Docker containers (2GB RAM, 2 CPUs each)

---

## 1. Dataset Description

The benchmark dataset consists of accommodation review data with the following schema:

| Column | Data Type | Description |
|--------|-----------|-------------|
| `review_id` | String | Unique identifier for each review |
| `accommodation_id` | String | Reference to the accommodation |
| `review_title` | String | Title of the review |
| `review_positive` | String | Positive aspects mentioned |
| `review_negative` | String | Negative aspects mentioned |
| `review_score` | Float | Numerical rating score |
| `review_helpful_votes` | Integer | Number of helpful votes received |
| `review_text` | String | Full review text content |
| `review_text_len` | Integer | Character length of review text |

---

## 2. HBase Schema Design

### 2.1 Table Structure

```
Table Name: benchmark
```

### 2.2 Row Key Design

```
Row Key: review_id (String, encoded as UTF-8 bytes)
```

**Design Rationale:**
- The `review_id` serves as a natural unique identifier
- String-based row keys allow for lexicographic ordering
- Enables efficient prefix scans for reviews with similar ID patterns

### 2.3 Column Family

```
Column Family: cf
Configuration:
  - max_versions: 1
  - compression: NONE
```

**Design Rationale:**
- Single column family (`cf`) for simplicity in benchmarking
- Single version retention reduces storage overhead
- No compression to measure raw I/O performance

### 2.4 Column Qualifiers

All data columns are stored under the `cf` column family:

```
cf:accommodation_id
cf:review_title
cf:review_positive
cf:review_negative
cf:review_score
cf:review_helpful_votes
cf:review_text
cf:review_text_len
```

### 2.5 Physical Data Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ Row Key (review_id)                                             │
├─────────────────────────────────────────────────────────────────┤
│ cf:accommodation_id │ cf:review_title │ cf:review_score │ ...   │
│ "hotel_12345"       │ "Great stay!"   │ "4.5"           │ ...   │
└─────────────────────────────────────────────────────────────────┘
```

### 2.6 HBase Queries

#### Point Lookup (Get)
```python
# Python (happybase)
table = connection.table('benchmark')
row = table.row(b'review_id_12345')

# HBase Shell equivalent
hbase> get 'benchmark', 'review_id_12345'
```

#### Range Scan
```python
# Python (happybase)
for key, data in table.scan(limit=100):
    print(key, data)

# HBase Shell equivalent
hbase> scan 'benchmark', {LIMIT => 100}
```

#### Prefix Scan
```python
# Python (happybase)
for key, data in table.scan(row_prefix=b'review_', limit=100):
    print(key, data)

# HBase Shell equivalent
hbase> scan 'benchmark', {ROWPREFIXFILTER => 'review_', LIMIT => 100}
```

#### Count (Full Table Scan)
```python
# Python (happybase)
count = sum(1 for _ in table.scan())

# HBase Shell equivalent
hbase> count 'benchmark'
```

#### Filtered Scan
```python
# Python (happybase)
filter_str = "SingleColumnValueFilter('cf', 'review_score', =, 'binary:4.5')"
for key, data in table.scan(filter=filter_str, limit=100):
    print(key, data)
```

---

## 3. MongoDB Document Model

### 3.1 Database and Collection

```
Database: benchmark
Collection: data
```

### 3.2 Document Structure

```json
{
  "_id": ObjectId("..."),
  "review_id": "review_12345",
  "accommodation_id": "hotel_67890",
  "review_title": "Amazing experience!",
  "review_positive": "Great location, friendly staff",
  "review_negative": "Room was small",
  "review_score": 4.5,
  "review_helpful_votes": 12,
  "review_text": "Full review content here...",
  "review_text_len": 245
}
```

### 3.3 Indexing Strategy

```javascript
// Primary index (automatic)
{ "_id": 1 }

// Secondary index on review_id
{ "review_id": 1 }
```

**Design Rationale:**
- Default `_id` index provides unique document identification
- Secondary index on `review_id` enables fast lookups by business key
- Single-field index sufficient for point queries and equality matches

### 3.4 MongoDB Queries

#### Point Lookup (Find One)
```python
# Python (pymongo)
doc = collection.find_one({"_id": ObjectId("...")})

# MongoDB Shell equivalent
db.data.findOne({_id: ObjectId("...")})
```

#### Range Scan (Find with Limit)
```python
# Python (pymongo)
docs = list(collection.find().limit(100))

# MongoDB Shell equivalent
db.data.find().limit(100)
```

#### Count Documents
```python
# Python (pymongo)
count = collection.count_documents({})

# MongoDB Shell equivalent
db.data.countDocuments({})
```

#### Aggregation (Group By)
```python
# Python (pymongo)
pipeline = [
    {"$group": {"_id": "$accommodation_id", "count": {"$sum": 1}}},
    {"$limit": 100}
]
results = list(collection.aggregate(pipeline))

# MongoDB Shell equivalent
db.data.aggregate([
    {$group: {_id: "$accommodation_id", count: {$sum: 1}}},
    {$limit: 100}
])
```

#### Filtered Query
```python
# Python (pymongo)
docs = list(collection.find({"review_score": {"$gte": 4.0}}).limit(100))

# MongoDB Shell equivalent
db.data.find({review_score: {$gte: 4.0}}).limit(100)
```

---

## 4. Performance Benchmark Results

### 4.1 Test Configuration

| Parameter | Value |
|-----------|-------|
| Dataset Size | 200,000 records |
| Warmup Iterations | 10 |
| Test Iterations | 100 (varies by test) |
| MongoDB Version | 7.0 |
| HBase Version | 2.5.7 |
| Container Memory | 2GB each |
| Container CPUs | 2 each |

### 4.2 Point Query Performance

Single row/document lookup by primary key.

| Metric | MongoDB | HBase | Difference |
|--------|---------|-------|------------|
| p50 (ms) | 0.230 | 0.871 | MongoDB 3.8x faster |
| p95 (ms) | 0.312 | 1.526 | MongoDB 4.9x faster |
| p99 (ms) | 0.384 | 8.354 | MongoDB 21.8x faster |
| Mean (ms) | 0.244 | 1.199 | MongoDB 4.9x faster |
| Std Dev (ms) | 0.094 | 2.042 | MongoDB more consistent |
| Min (ms) | 0.178 | 0.656 | - |
| Max (ms) | 1.097 | 19.960 | - |
| **Throughput (ops/sec)** | **4,100.68** | **834.32** | **MongoDB 4.9x higher** |

### 4.3 Range Scan Performance (100 Rows)

Sequential scan returning 100 rows/documents.

| Metric | MongoDB | HBase | Difference |
|--------|---------|-------|------------|
| p50 (ms) | 0.614 | 4.173 | MongoDB 6.8x faster |
| p95 (ms) | 0.690 | 6.278 | MongoDB 9.1x faster |
| p99 (ms) | 1.152 | 23.204 | MongoDB 20.1x faster |
| Mean (ms) | 0.646 | 4.793 | MongoDB 7.4x faster |
| Std Dev (ms) | 0.215 | 2.824 | MongoDB more consistent |
| Min (ms) | 0.553 | 3.180 | - |
| Max (ms) | 2.657 | 23.478 | - |
| **Throughput (ops/sec)** | **1,548.48** | **208.65** | **MongoDB 7.4x higher** |

### 4.4 Range Scan Performance (1,000 Rows)

Sequential scan returning 1,000 rows/documents.

| Metric | MongoDB | HBase | Difference |
|--------|---------|-------|------------|
| p50 (ms) | 4.318 | 16.429 | MongoDB 3.8x faster |
| p95 (ms) | 4.505 | 22.826 | MongoDB 5.1x faster |
| p99 (ms) | 4.618 | 23.740 | MongoDB 5.1x faster |
| Mean (ms) | 4.331 | 16.849 | MongoDB 3.9x faster |
| Std Dev (ms) | 0.111 | 3.614 | MongoDB more consistent |
| Min (ms) | 4.126 | 12.290 | - |
| Max (ms) | 4.624 | 24.182 | - |
| **Throughput (ops/sec)** | **230.88** | **59.35** | **MongoDB 3.9x higher** |

### 4.5 Count Query Performance

Full table/collection count operation.

| Metric | MongoDB | HBase | Difference |
|--------|---------|-------|------------|
| p50 (ms) | 48.832 | 2,616.199 | MongoDB 53.6x faster |
| p95 (ms) | 51.161 | 2,652.562 | MongoDB 51.8x faster |
| p99 (ms) | 51.428 | 2,657.016 | MongoDB 51.7x faster |
| Mean (ms) | 49.067 | 2,618.283 | MongoDB 53.4x faster |
| Std Dev (ms) | 1.047 | 27.525 | MongoDB more consistent |
| Min (ms) | 47.460 | 2,588.129 | - |
| Max (ms) | 51.495 | 2,658.129 | - |
| **Throughput (ops/sec)** | **20.38** | **0.38** | **MongoDB 53.6x higher** |

### 4.6 Aggregation / Prefix Scan Performance

MongoDB aggregation (group by) vs HBase prefix scan.

| Metric | MongoDB (Aggregation) | HBase (Prefix Scan) |
|--------|----------------------|---------------------|
| p50 (ms) | 131.340 | 3.312 |
| p95 (ms) | 185.966 | 4.506 |
| p99 (ms) | 201.742 | 11.533 |
| Mean (ms) | 137.929 | 3.627 |
| Std Dev (ms) | 18.874 | 2.075 |
| Min (ms) | 121.905 | 2.598 |
| Max (ms) | 202.645 | 17.568 |
| **Throughput (ops/sec)** | **7.25** | **275.75** |

*Note: These are different operations (aggregation vs prefix scan) and not directly comparable.*

---

## 5. HBase vs MongoDB Comparison

### 5.1 Performance Summary Table

| Test Scenario | MongoDB p50 (ms) | HBase p50 (ms) | Winner | Speedup Factor |
|---------------|------------------|----------------|--------|----------------|
| Point Query | 0.230 | 0.871 | MongoDB | 3.8x |
| Range Scan (100) | 0.614 | 4.173 | MongoDB | 6.8x |
| Range Scan (1000) | 4.318 | 16.429 | MongoDB | 3.8x |
| Count All | 48.832 | 2,616.199 | MongoDB | 53.6x |

### 5.2 Throughput Comparison

| Test Scenario | MongoDB (ops/sec) | HBase (ops/sec) | Winner | Ratio |
|---------------|-------------------|-----------------|--------|-------|
| Point Query | 4,100.68 | 834.32 | MongoDB | 4.9x |
| Range Scan (100) | 1,548.48 | 208.65 | MongoDB | 7.4x |
| Range Scan (1000) | 230.88 | 59.35 | MongoDB | 3.9x |
| Count All | 20.38 | 0.38 | MongoDB | 53.6x |

### 5.3 Latency Consistency (Standard Deviation)

| Test Scenario | MongoDB Std Dev (ms) | HBase Std Dev (ms) | More Consistent |
|---------------|---------------------|-------------------|-----------------|
| Point Query | 0.094 | 2.042 | MongoDB (21.7x) |
| Range Scan (100) | 0.215 | 2.824 | MongoDB (13.1x) |
| Range Scan (1000) | 0.111 | 3.614 | MongoDB (32.6x) |
| Count All | 1.047 | 27.525 | MongoDB (26.3x) |

### 5.4 Feature Comparison

| Feature | MongoDB | HBase |
|---------|---------|-------|
| **Data Model** | Document (JSON/BSON) | Wide-column (Key-Value) |
| **Query Language** | Rich query API, Aggregation Framework | Get, Scan, Filters |
| **Secondary Indexes** | Native support | Limited (requires Phoenix) |
| **Aggregations** | Built-in pipeline | Requires MapReduce/Spark |
| **Transactions** | Multi-document ACID | Row-level only |
| **Scalability** | Horizontal (sharding) | Horizontal (region splits) |
| **Consistency** | Tunable | Strong (single row) |
| **Best For** | General purpose, flexible schemas | Time-series, sparse data, massive scale |

---

## 6. Conclusion

Based on the benchmark results with a 200,000-record dataset in a Docker environment, **MongoDB significantly outperforms HBase** across all tested query patterns:

### Key Findings

1. **Point Queries:** MongoDB delivers 4.9x higher throughput (4,100 vs 834 ops/sec) with 3.8x lower latency. This demonstrates MongoDB's efficient B-tree indexing and document retrieval mechanism.

2. **Range Scans:** MongoDB maintains a consistent 3.8-7.4x performance advantage across different scan sizes. The gap widens for smaller scans (100 rows) where MongoDB's cursor efficiency shines.

3. **Count Operations:** The most dramatic difference occurs in full-table counts, where MongoDB is 53.6x faster. MongoDB maintains collection statistics metadata, while HBase requires a complete table scan.

4. **Latency Consistency:** MongoDB exhibits significantly lower variance (13-32x lower standard deviation), making it more predictable for latency-sensitive applications.

### Caveats

- **Scale:** HBase is designed for petabyte-scale deployments across hundreds of nodes. This single-node Docker benchmark does not reflect HBase's distributed performance characteristics.

- **Write Performance:** This benchmark focused on read operations. HBase's log-structured merge-tree (LSM) architecture often excels at write-heavy workloads.

- **Use Case Fit:** HBase remains the better choice for:
  - Time-series data with row-key-based access patterns
  - Sparse, wide tables with billions of rows
  - Integration with Hadoop ecosystem (HDFS, Spark)

### Recommendation

For applications requiring:
- **Flexible queries, aggregations, and moderate scale** → Choose **MongoDB**
- **Massive scale, simple key-based access, Hadoop integration** → Choose **HBase**

In this benchmark scenario (200K records, mixed query patterns, containerized environment), MongoDB is the clear performance winner with superior throughput, lower latency, and more consistent response times.
