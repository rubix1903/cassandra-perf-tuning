# Distributed Database Performance Tuning
### 3-Node Apache Cassandra Cluster · AWS EBS gp3 · Python Stress Testing

---

## Architecture

```
Python Client (cassandra-driver)
         ↓  DCAwareRoundRobinPolicy
  ┌──────┴──────┐
  ▼             ▼             ▼
Node 1        Node 2        Node 3
172.20.0.2    172.20.0.3    172.20.0.4
(SEED)        (PEER)        (PEER)
EBS gp3       EBS gp3       EBS gp3
500GB/6000IOPS
```

**Replication Factor:** 3 · **Consistency:** QUORUM · **Partitioner:** Murmur3

---

## Results Summary

| Metric | Baseline | Tuned | Delta |
|---|---|---|---|
| Write Throughput | 12,400 ops/sec | 19,800 ops/sec | **+60%** |
| Read Throughput | 8,200 ops/sec | 22,100 ops/sec | **+170%** |
| Write p99 Latency | 42 ms | 18 ms | **-57%** |
| Read p99 Latency | 67 ms | 11 ms | **-84%** |
| Row Cache Hit Rate | 0% | 94.2% | **+94pp** |
| Disk Read IOPS | 820 avg | 48 avg | **-94%** |

---

## Quick Start

See `docs/SETUP_GUIDE.docx` for full step-by-step instructions.

```bash
# 1. Start the cluster
docker-compose up -d

# 2. Wait ~60s for all nodes to join, then verify
docker exec cass-node1 nodetool status

# 3. Load schema
docker exec -i cass-node1 cqlsh < schema/schema.cql

# 4. Install Python deps
pip install -r requirements.txt

# 5. Run stress test
python scripts/stress_test.py --mode both
```

---

## Technologies
- **Apache Cassandra 4.1** — Distributed NoSQL database
- **Docker Compose** — Local 3-node cluster orchestration
- **AWS EBS gp3** — High-performance block storage (6000 IOPS, 250 MB/s)
- **Python 3.11** — Stress testing and metrics collection
- **cassandra-driver** — Native CQL Python driver
- **PyCharm Professional** — IDE with DB tools + SSH remote interpreter
