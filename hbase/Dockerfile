FROM eclipse-temurin:11-jdk

LABEL maintainer="benchmark"
LABEL description="HBase standalone for benchmarking"

# HBase version
ENV HBASE_VERSION=2.5.7
ENV HBASE_HOME=/opt/hbase
ENV PATH=$PATH:$HBASE_HOME/bin

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    procps \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Download and install HBase
RUN curl -fSL "https://archive.apache.org/dist/hbase/${HBASE_VERSION}/hbase-${HBASE_VERSION}-bin.tar.gz" -o /tmp/hbase.tar.gz \
    && tar -xzf /tmp/hbase.tar.gz -C /opt \
    && mv /opt/hbase-${HBASE_VERSION} ${HBASE_HOME} \
    && rm /tmp/hbase.tar.gz

# Create data directories
RUN mkdir -p /data/hbase /data/zookeeper /data/hbase-tmp

# Copy configuration
COPY hbase-site.xml ${HBASE_HOME}/conf/hbase-site.xml

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Set Java options for better performance
ENV HBASE_OPTS="-XX:+UseG1GC -XX:MaxGCPauseMillis=100"
ENV HBASE_HEAPSIZE=1G

# Expose ports
# 2181 - ZooKeeper (embedded)
# 8080 - REST API
# 9090 - Thrift
# 16000 - Master
# 16010 - Master Web UI
# 16020 - RegionServer
# 16030 - RegionServer Web UI
EXPOSE 2181 8080 9090 16000 16010 16020 16030

VOLUME ["/data"]

ENTRYPOINT ["/entrypoint.sh"]
