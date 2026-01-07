#!/bin/bash
set -e

echo "Starting HBase standalone mode..."

# Start HBase (includes embedded ZooKeeper)
${HBASE_HOME}/bin/start-hbase.sh

# Wait for HBase Master to be ready
echo "Waiting for HBase Master to start..."
for i in {1..60}; do
    if ${HBASE_HOME}/bin/hbase shell -n <<< "status" 2>/dev/null | grep -q "1 active master"; then
        echo "HBase Master is ready!"
        break
    fi
    echo "  Attempt $i/60 - waiting..."
    sleep 2
done

# Start Thrift server in background
echo "Starting Thrift server on port 9090..."
${HBASE_HOME}/bin/hbase thrift start -p 9090 &
THRIFT_PID=$!

# Start REST server in background
echo "Starting REST server on port 8080..."
${HBASE_HOME}/bin/hbase rest start -p 8080 &
REST_PID=$!

# Wait for Thrift to be ready
echo "Waiting for Thrift server..."
for i in {1..30}; do
    if nc -z localhost 9090 2>/dev/null; then
        echo "Thrift server is ready!"
        break
    fi
    sleep 1
done

echo ""
echo "============================================"
echo "HBase is ready!"
echo "  Master UI:        http://localhost:16010"
echo "  Thrift API:       localhost:9090"
echo "  REST API:         http://localhost:8080"
echo "============================================"
echo ""

# Keep container running and handle shutdown
trap "echo 'Shutting down...'; ${HBASE_HOME}/bin/stop-hbase.sh; exit 0" SIGTERM SIGINT

# Tail HBase logs to keep container alive
tail -f ${HBASE_HOME}/logs/*.log 2>/dev/null || while true; do sleep 1000; done
