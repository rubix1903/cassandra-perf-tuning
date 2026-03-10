#!/bin/bash
# =============================================================
# ec2_setup.sh — Run this on EACH EC2 instance after launching
# Edit NODE_IP and SEED_IP before running
# =============================================================

NODE_IP="172.31.66.92"      # e.g. 10.0.1.10  (find in EC2 console)
SEED_IP="172.31.66.92"     # always node1's private IP for all 3 nodes

# ── STEP 1: Update and install Java ──────────────────────────
sudo apt update && sudo apt upgrade -y
sudo apt install -y openjdk-11-jdk
java -version

# ── STEP 2: Install Cassandra 4.1 ────────────────────────────
echo "deb https://debian.cassandra.apache.org 41x main" | sudo tee /etc/apt/sources.list.d/cassandra.sources.list
curl https://downloads.apache.org/cassandra/KEYS | sudo apt-key add -
sudo apt update && sudo apt install -y cassandra
sudo systemctl stop cassandra

# ── STEP 3: Install Python 3.11 and packages ─────────────────
sudo apt install -y python3.11 python3-pip git
pip3 install cassandra-driver faker pandas matplotlib tqdm numpy boto3

# ── STEP 4: Configure Cassandra ───────────────────────────────
sudo tee /etc/cassandra/cassandra.yaml > /dev/null <<EOF
cluster_name: 'PerfCluster'
num_tokens: 256

seed_provider:
  - class_name: org.apache.cassandra.locator.SimpleSeedProvider
    parameters:
      - seeds: "$SEED_IP"

data_file_directories:
  - /var/lib/cassandra/data
commitlog_directory: /var/lib/cassandra/commitlog
saved_caches_directory: /var/lib/cassandra/saved_caches
hints_directory: /var/lib/cassandra/hints

listen_address: $NODE_IP
rpc_address: 0.0.0.0
broadcast_rpc_address: $NODE_IP

native_transport_port: 9042
storage_port: 7000

endpoint_snitch: Ec2Snitch

partitioner: org.apache.cassandra.dht.Murmur3Partitioner

disk_optimization_strategy: ssd
concurrent_reads: 32
concurrent_writes: 32

row_cache_size_in_mb: 512
row_cache_class_name: org.apache.cassandra.cache.OHCProvider
key_cache_size_in_mb: 256

compaction_throughput_mb_per_sec: 64
concurrent_compactors: 2

commitlog_sync: periodic
commitlog_sync_period_in_ms: 10000

authenticator: AllowAllAuthenticator
authorizer: AllowAllAuthorizer
EOF

# ── STEP 5: Set JVM heap ──────────────────────────────────────
sudo tee /etc/cassandra/jvm.options > /dev/null <<EOF
-Xms2G
-Xmx2G
-Xmn512M
-XX:+UseG1GC
-XX:G1RSetUpdatingPauseTimePercent=5
-XX:MaxGCPauseMillis=300
-XX:MaxDirectMemorySize=1G
-da
EOF

# ── STEP 6: Start Cassandra ───────────────────────────────────
sudo systemctl enable cassandra
sudo systemctl start cassandra

echo ""
echo "Done. Wait 60 seconds then run: nodetool status"
echo "Start node1 first, wait 60s, then node2, wait, then node3"