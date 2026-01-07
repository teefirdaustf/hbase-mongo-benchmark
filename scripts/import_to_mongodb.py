#!/usr/bin/env python3
"""
Import parquet files into MongoDB for benchmarking.
"""

import os
import sys
import time
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
from pymongo import MongoClient
from pymongo.errors import BulkWriteError
from tqdm import tqdm


# Configuration
MONGODB_HOST = os.getenv("MONGODB_HOST", "localhost")
MONGODB_PORT = int(os.getenv("MONGODB_PORT", 27017))
MONGODB_DB = os.getenv("MONGODB_DB", "benchmark")
MONGODB_COLLECTION = os.getenv("MONGODB_COLLECTION", "data")
DATA_DIR = os.getenv("DATA_DIR", "./data")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 5000))


def get_parquet_files(data_dir: str) -> list[Path]:
    """Find all parquet files in the data directory."""
    data_path = Path(data_dir)
    parquet_files = list(data_path.glob("*.parquet"))
    if not parquet_files:
        print(f"No parquet files found in {data_dir}")
        sys.exit(1)
    return sorted(parquet_files)


def connect_mongodb() -> MongoClient:
    """Connect to MongoDB and return client."""
    client = MongoClient(MONGODB_HOST, MONGODB_PORT)
    # Test connection
    client.admin.command("ping")
    print(f"Connected to MongoDB at {MONGODB_HOST}:{MONGODB_PORT}")
    return client


def import_parquet_to_mongodb(client: MongoClient, parquet_files: list[Path]) -> dict:
    """Import parquet files into MongoDB."""
    db = client[MONGODB_DB]
    collection = db[MONGODB_COLLECTION]

    # Drop existing collection for clean import
    collection.drop()
    print(f"Dropped existing collection '{MONGODB_COLLECTION}'")

    total_records = 0
    total_time = 0

    for parquet_file in parquet_files:
        print(f"\nProcessing: {parquet_file.name}")

        # Read parquet file
        df = pd.read_parquet(parquet_file)
        records = df.to_dict(orient="records")
        num_records = len(records)

        print(f"  Records: {num_records}")
        print(f"  Columns: {list(df.columns)}")

        # Insert in batches
        start_time = time.time()

        for i in tqdm(range(0, num_records, BATCH_SIZE), desc="  Importing"):
            batch = records[i:i + BATCH_SIZE]
            try:
                collection.insert_many(batch, ordered=False)
            except BulkWriteError as e:
                print(f"  Warning: Some documents failed to insert: {e.details}")

        elapsed = time.time() - start_time
        total_time += elapsed
        total_records += num_records

        print(f"  Time: {elapsed:.2f}s ({num_records / elapsed:.0f} records/sec)")

    # Create index on first column (assuming it's a key)
    first_col = df.columns[0]
    print(f"\nCreating index on '{first_col}'...")
    collection.create_index(first_col)

    return {
        "total_records": total_records,
        "total_time": total_time,
        "throughput": total_records / total_time if total_time > 0 else 0,
        "collection": MONGODB_COLLECTION,
        "database": MONGODB_DB
    }


def main():
    print("=" * 60)
    print("MongoDB Parquet Import")
    print("=" * 60)

    # Find parquet files
    parquet_files = get_parquet_files(DATA_DIR)
    print(f"\nFound {len(parquet_files)} parquet file(s):")
    for f in parquet_files:
        print(f"  - {f.name}")

    # Connect to MongoDB
    try:
        client = connect_mongodb()
    except Exception as e:
        print(f"Failed to connect to MongoDB: {e}")
        print("Make sure MongoDB is running: docker-compose up -d mongodb")
        sys.exit(1)

    # Import data
    try:
        stats = import_parquet_to_mongodb(client, parquet_files)
    finally:
        client.close()

    # Print summary
    print("\n" + "=" * 60)
    print("Import Summary")
    print("=" * 60)
    print(f"Database:      {stats['database']}")
    print(f"Collection:    {stats['collection']}")
    print(f"Total Records: {stats['total_records']:,}")
    print(f"Total Time:    {stats['total_time']:.2f}s")
    print(f"Throughput:    {stats['throughput']:,.0f} records/sec")
    print("=" * 60)


if __name__ == "__main__":
    main()
