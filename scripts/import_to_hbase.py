#!/usr/bin/env python3
"""
Import parquet files into HBase for benchmarking.
"""

import os
import sys
import time
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import happybase
from tqdm import tqdm


# Configuration
HBASE_HOST = os.getenv("HBASE_HOST", "localhost")
HBASE_THRIFT_PORT = int(os.getenv("HBASE_THRIFT_PORT", 9090))
HBASE_TABLE = os.getenv("HBASE_TABLE", "benchmark")
HBASE_CF = os.getenv("HBASE_CF", "cf")  # Column family
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


def connect_hbase() -> happybase.Connection:
    """Connect to HBase via Thrift and return connection."""
    connection = happybase.Connection(HBASE_HOST, port=HBASE_THRIFT_PORT)
    connection.open()
    print(f"Connected to HBase at {HBASE_HOST}:{HBASE_THRIFT_PORT}")
    return connection


def create_table(connection: happybase.Connection, table_name: str, column_family: str):
    """Create HBase table if it doesn't exist."""
    tables = [t.decode() for t in connection.tables()]

    if table_name in tables:
        print(f"Dropping existing table '{table_name}'...")
        connection.disable_table(table_name)
        connection.delete_table(table_name)

    print(f"Creating table '{table_name}' with column family '{column_family}'...")
    connection.create_table(
        table_name,
        {column_family: dict(max_versions=1, compression='NONE')}
    )


def import_parquet_to_hbase(connection: happybase.Connection, parquet_files: list[Path]) -> dict:
    """Import parquet files into HBase."""
    # Create table
    create_table(connection, HBASE_TABLE, HBASE_CF)
    table = connection.table(HBASE_TABLE)

    total_records = 0
    total_time = 0
    cf_prefix = f"{HBASE_CF}:".encode()

    for parquet_file in parquet_files:
        print(f"\nProcessing: {parquet_file.name}")

        # Read parquet file
        df = pd.read_parquet(parquet_file)
        num_records = len(df)
        columns = list(df.columns)

        # Use first column as row key
        row_key_col = columns[0]
        value_cols = columns[1:] if len(columns) > 1 else columns

        print(f"  Records: {num_records}")
        print(f"  Row key column: {row_key_col}")
        print(f"  Value columns: {value_cols}")

        # Convert DataFrame to list of tuples (row_key, data_dict)
        start_time = time.time()

        # Process in batches
        for batch_start in tqdm(range(0, num_records, BATCH_SIZE), desc="  Importing"):
            batch_end = min(batch_start + BATCH_SIZE, num_records)
            batch_df = df.iloc[batch_start:batch_end]

            with table.batch(batch_size=BATCH_SIZE) as batch:
                for _, row in batch_df.iterrows():
                    # Generate row key from first column
                    row_key = str(row[row_key_col]).encode()

                    # Prepare column data
                    data = {}
                    for col in value_cols:
                        value = row[col]
                        # Convert value to string, handle None/NaN
                        if pd.isna(value):
                            str_value = ""
                        else:
                            str_value = str(value)
                        col_key = f"{HBASE_CF}:{col}".encode()
                        data[col_key] = str_value.encode()

                    batch.put(row_key, data)

        elapsed = time.time() - start_time
        total_time += elapsed
        total_records += num_records

        print(f"  Time: {elapsed:.2f}s ({num_records / elapsed:.0f} records/sec)")

    return {
        "total_records": total_records,
        "total_time": total_time,
        "throughput": total_records / total_time if total_time > 0 else 0,
        "table": HBASE_TABLE,
        "column_family": HBASE_CF
    }


def main():
    print("=" * 60)
    print("HBase Parquet Import")
    print("=" * 60)

    # Find parquet files
    parquet_files = get_parquet_files(DATA_DIR)
    print(f"\nFound {len(parquet_files)} parquet file(s):")
    for f in parquet_files:
        print(f"  - {f.name}")

    # Connect to HBase
    try:
        connection = connect_hbase()
    except Exception as e:
        print(f"Failed to connect to HBase: {e}")
        print("Make sure HBase is running: docker-compose up -d hbase")
        print("And that the Thrift server is started.")
        print("\nTo start Thrift server manually:")
        print("  docker exec -it benchmark-hbase /opt/hbase/bin/hbase thrift start &")
        sys.exit(1)

    # Import data
    try:
        stats = import_parquet_to_hbase(connection, parquet_files)
    finally:
        connection.close()

    # Print summary
    print("\n" + "=" * 60)
    print("Import Summary")
    print("=" * 60)
    print(f"Table:         {stats['table']}")
    print(f"Column Family: {stats['column_family']}")
    print(f"Total Records: {stats['total_records']:,}")
    print(f"Total Time:    {stats['total_time']:.2f}s")
    print(f"Throughput:    {stats['throughput']:,.0f} records/sec")
    print("=" * 60)


if __name__ == "__main__":
    main()
