"""
Parses nodetool output and saves results to CSV
------------------------------------------------------------
Ran nodetool commands against the Docker cluster and
stored cache hit rates, compaction stats, and table-level
read/write latencies into results/node_metrics.csv (.gitignore)
"""

import subprocess
import csv
import re
import os
from datetime import datetime

NODES = {
    "node1": "cass-node1",
    "node2": "cass-node2",
    "node3": "cass-node3",
}
KEYSPACE = "perf_test"
TABLES   = ["sensor_events", "user_profiles"]
OUTFILE  = "results/node_metrics.csv"


def run_nodetool(container: str, *args) -> str:
    """Executing nodetool inside a Docker container and return stdout."""
    cmd = ["docker", "exec", container, "nodetool"] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return result.stdout


def parse_info(output: str) -> dict:
    """Extracts row cache and key cache stats from `nodetool info`."""
    data = {}
    patterns = {
        "row_cache_entries":  r"Row Cache\s+:\s+(\d+) entries",
        "row_cache_size_mb":  r"Row Cache\s+:\s+\S+.*?(\d+(?:\.\d+)?)\s*MB",
        "row_cache_hit_rate": r"Row Cache.*?(\d+(?:\.\d+)?) recent hit rate",
        "key_cache_entries":  r"Key Cache\s+:\s+(\d+) entries",
        "key_cache_hit_rate": r"Key Cache.*?(\d+(?:\.\d+)?) recent hit rate",
        "heap_used_mb":       r"Heap Memory.*?(\d+(?:\.\d+)?)/",
        "load_mb":            r"Load\s+:\s+(\d+(?:\.\d+)?)\s*MB",
    }
    for key, pattern in patterns.items():
        m = re.search(pattern, output, re.IGNORECASE)
        data[key] = float(m.group(1)) if m else 0.0
    return data


def parse_cfstats(output: str, table: str) -> dict:
    """Extract per-table stats from `nodetool cfstats`."""
    data = {}
    in_table = False
    for line in output.splitlines():
        if f"Table: {table}" in line:
            in_table = True
        if in_table:
            if "Read Latency:" in line:
                m = re.search(r"([\d.]+) ms", line)
                data[f"{table}_read_latency_ms"] = float(m.group(1)) if m else 0.0
            if "Write Latency:" in line:
                m = re.search(r"([\d.]+) ms", line)
                data[f"{table}_write_latency_ms"] = float(m.group(1)) if m else 0.0
            if "Row cache hit rate" in line:
                m = re.search(r"([\d.]+)", line)
                data[f"{table}_row_cache_hit_rate"] = float(m.group(1)) if m else 0.0
            if "SSTable count" in line:
                m = re.search(r"(\d+)", line)
                data[f"{table}_sstable_count"] = int(m.group(1)) if m else 0
            if "Table:" in line and in_table and table not in line:
                break  # moved past our table
    return data


def collect():
    os.makedirs("results", exist_ok=True)
    rows = []

    for node_name, container in NODES.items():
        print(f"  Collecting metrics from {node_name} ({container})...")
        row = {"timestamp": datetime.now().isoformat(), "node": node_name}

        # nodetool info
        info_out = run_nodetool(container, "info")
        row.update(parse_info(info_out))

        # nodetool cfstats per table
        for table in TABLES:
            cf_out = run_nodetool(container, "cfstats", f"{KEYSPACE}.{table}")
            row.update(parse_cfstats(cf_out, table))

        rows.append(row)
        print(f"    ✓ {node_name}: row_cache_hit={row.get('row_cache_hit_rate', 0):.2f}")

    if not rows:
        print("No data collected.")
        return

    fieldnames = list(rows[0].keys())
    write_header = not os.path.exists(OUTFILE)
    with open(OUTFILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerows(rows)

    print(f"\n  💾 Metrics saved → {OUTFILE}")


if __name__ == "__main__":
    print("📊 Collecting Cassandra node metrics...\n")
    collect()
