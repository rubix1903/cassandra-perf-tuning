# Distributed Database Performance Tuning
### 3-Node Apache Cassandra Cluster · Python Stress Testing

A hands-on project where I deployed a 3-node Apache Cassandra cluster, stress-tested it with a custom Python benchmark, and tuned the database to reduce latency and improve throughput.

---

## Architecture

```
Python Client (cassandra-driver)
         ↓  DCAwareRoundRobinPolicy
  ┌──────┴────────────┴──────┐
  ▼             ▼             ▼
Node 1        Node 2        Node 3
172.20.0.2    172.20.0.3    172.20.0.4
(SEED)        (PEER)        (PEER)
```

**Replication Factor:** 3 · **Consistency:** QUORUM · **Partitioner:** Murmur3


## Results Summary

| Metric             | Baseline     | Tuned         | Delta     |
|--------------------|--------------|---------------|-----------|
| Write Throughput   | 43.9 ops/sec | 90 ops/sec    | **+107%** |
| Read Throughput    | 312 ops/sec  | 482.1 ops/sec | **+54%**  |
| Write Mean Latency | 217.0 ms     | 144.8 ms      | **-33%**  |
| Write p95 Latency  | 351.3 ms     | 219.4 ms      | **-38%**  |
| Write p99 Latency  | 546 ms       | 301.1 ms      | **-45%**  |
| Read Mean Latency  | 47.96 ms     | 31.47 ms      | **-34%**  |
| Read p95 Latency   | 115.7 ms     | 49.1 ms       | **-58%**  |
| Read p99 Latency   | 186.3 ms     | 62.5 ms       | **-66%**  |
| Write Max Latency  | 9318 ms      | 2481 ms       | **-73%**  |
| Errors (timeouts)  | 373          | 0             | **-100%** |

---

## Quick Start

```bash
# 1. Start the cluster
docker-compose up -d

# 2. Wait ~60s for all nodes to join, then verify health-check (troubleshoot wsl memory | check port conflicts | flush network )
docker exec cass-node1 nodetool status

# 3. Load schema
Get-Content schema/schema.cql | docker exec -i cass-node1 cqlsh 

# 4. Install Python deps
pip install -r requirements.txt

# 5. Run stress test
python scripts/stress_test.py --mode both
```

---

## Challenges
- **WSL2 networking** — static IPs in docker-compose don't work reliably on Windows with the WSL2 backend. Switched to hostname-based seed discovery and Docker's internal DNS.
- **Port conflict on node 1** — all 3 nodes kept failing to form a ring. Something else on the machine was already bound to port 9042. Killed that process, flushed Docker networks, and restarted fresh — all 3 nodes came up healthy with RF=3.
- **Python 3.13** — cassandra-driver depends on asyncore which was removed in Python 3.12+. Downgraded to Python 3.11 for this project.
- **Heap sizing** — reduced MAX_HEAP_SIZE to 512MB per node so all 3 run simultaneously on a laptop without competing for RAM.

---

## Technologies
- **Apache Cassandra 4.1** — Distributed NoSQL database
- **Docker Compose** — Local 3-node cluster orchestration
- **AWS EBS gp3** — High-performance block storage (6000 IOPS, 250 MB/s)
- **Python 3.11** — Stress testing and metrics collection
- **cassandra-driver** — Native CQL Python driver
- **PyCharm Professional** — IDE with DB tools + SSH remote interpreter
