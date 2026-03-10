"""
Cassandra's Multi-threaded Benchmark
----------------------------------------
--mode write|read|both
"""

import uuid
import time
import statistics
import threading
import argparse
import csv
import os
from datetime import datetime, timezone
from cassandra.cluster import Cluster
from cassandra.policies import DCAwareRoundRobinPolicy, RetryPolicy
from cassandra import ConsistencyLevel
from cassandra.query import BatchStatement, BatchType
from faker import Faker
from tqdm import tqdm
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

# ── CONFIG ──────────────────────────────────────────────────────
CONTACT_POINTS = ["127.0.0.1"]   # Change to EC2 IPs for AWS
KEYSPACE       = "perf_test"
WRITE_OPS      = 50_000          # Number of batch-write calls
READ_OPS       = 20_000          # Number of single-partition reads
THREADS        = 16
BATCH_SIZE     = 50              # Rows per batch write
CONFIG_TAG     = "tuned"         # "baseline" or "tuned" — label for results

fake = Faker()

# ── CONNECTION ──────────────────────────────────────────────────
class CassandraStressTest:
    def __init__(self):
        print(f"\n🔌 Connecting to Cassandra at {CONTACT_POINTS}...")
        self.cluster = Cluster(
            contact_points=CONTACT_POINTS,
            load_balancing_policy=DCAwareRoundRobinPolicy(local_dc="datacenter1"),
            default_retry_policy=RetryPolicy(),
            protocol_version=5,
            connect_timeout=30,
        )
        self.session = self.cluster.connect(KEYSPACE)
        self.session.default_consistency_level = ConsistencyLevel.QUORUM
        print("✅  Connected.\n")

        self.write_latencies = []
        self.read_latencies  = []
        self.errors = 0
        self._lock = threading.Lock()
        self._sample_device_ids = []

        # Prepare statements once (avoids repeated parsing overhead)
        self._prepare_statements()

    def _prepare_statements(self):
        self.insert_stmt = self.session.prepare("""
            INSERT INTO sensor_events
              (device_id, event_time, sensor_type, value, metadata)
            VALUES (?, ?, ?, ?, ?)
            USING TTL 86400
        """)
        self.select_stmt = self.session.prepare("""
            SELECT * FROM sensor_events
            WHERE device_id = ?
            LIMIT 10
        """)
        self.insert_user = self.session.prepare("""
            INSERT INTO user_profiles
              (user_id, username, email, region, created_at, last_login, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """)
        self.select_user = self.session.prepare("""
            SELECT * FROM user_profiles WHERE user_id = ?
        """)

    # ── WRITE WORKER ────────────────────────────────────────────
    def _write_worker(self, count, progress_bar, device_ids_out):
        local_ids = []
        for _ in range(count):
            batch = BatchStatement(batch_type=BatchType.UNLOGGED)
            ids_in_batch = []
            for _ in range(BATCH_SIZE):
                did = uuid.uuid4()
                ids_in_batch.append(did)
                batch.add(self.insert_stmt, (
                    did,
                    datetime.now(timezone.utc),
                    fake.random_element(["temp", "humidity", "pressure", "voltage"]),
                    fake.pyfloat(min_value=0.0, max_value=100.0, right_digits=4),
                    {"location": fake.city(), "unit": fake.currency_code()}
                ))
            t0 = time.perf_counter()
            try:
                self.session.execute(batch)
                lat = (time.perf_counter() - t0) * 1000
                with self._lock:
                    self.write_latencies.append(lat)
                    local_ids.extend(ids_in_batch)
            except Exception as e:
                with self._lock:
                    self.errors += 1
            progress_bar.update(1)
        with self._lock:
            device_ids_out.extend(local_ids[:50])  # keep sample for reads

    # ── READ WORKER ─────────────────────────────────────────────
    def _read_worker(self, device_ids, count, progress_bar):
        for did in device_ids[:count]:
            t0 = time.perf_counter()
            try:
                rows = list(self.session.execute(self.select_stmt, (did,)))
                lat = (time.perf_counter() - t0) * 1000
                with self._lock:
                    self.read_latencies.append(lat)
            except Exception:
                with self._lock:
                    self.errors += 1
            progress_bar.update(1)

    # ── RUN WRITE STRESS ────────────────────────────────────────
    def run_write_stress(self):
        print(f"▶  WRITE STRESS — {WRITE_OPS * BATCH_SIZE:,} total rows "
              f"via {THREADS} threads (batch size={BATCH_SIZE})")
        t_start = time.time()
        threads = []
        per_thread = WRITE_OPS // THREADS
        device_ids_collected = []

        with tqdm(total=WRITE_OPS, desc="  Writing", unit="batch",
                  bar_format="{l_bar}{bar:30}{r_bar}") as pbar:
            for _ in range(THREADS):
                t = threading.Thread(
                    target=self._write_worker,
                    args=(per_thread, pbar, device_ids_collected)
                )
                threads.append(t)
                t.start()
            for t in threads:
                t.join()

        elapsed = time.time() - t_start
        self._sample_device_ids = device_ids_collected
        stats = self._report("WRITE", self.write_latencies, elapsed)
        self._save_results("WRITE", stats)
        return stats

    # ── RUN READ STRESS ─────────────────────────────────────────
    def run_read_stress(self):
        if not self._sample_device_ids:
            print("⚠  No device IDs available. Run write stress first.")
            return

        print(f"▶  READ STRESS — {READ_OPS:,} lookups via {THREADS} threads")
        t_start = time.time()
        threads = []
        per_thread = READ_OPS // THREADS
        chunk = max(1, len(self._sample_device_ids) // THREADS)

        with tqdm(total=READ_OPS, desc="  Reading", unit="op",
                  bar_format="{l_bar}{bar:30}{r_bar}") as pbar:
            for i in range(THREADS):
                ids_chunk = self._sample_device_ids[i*chunk:(i+1)*chunk]
                if not ids_chunk:
                    ids_chunk = self._sample_device_ids
                t = threading.Thread(
                    target=self._read_worker,
                    args=(ids_chunk, per_thread, pbar)
                )
                threads.append(t)
                t.start()
            for t in threads:
                t.join()

        elapsed = time.time() - t_start
        stats = self._report("READ", self.read_latencies, elapsed)
        self._save_results("READ", stats)
        return stats

    # ── STATS REPORT ────────────────────────────────────────────
    def _report(self, op, latencies, elapsed):
        if not latencies:
            print(f"  No {op} latencies recorded.")
            return {}
        lats = sorted(latencies)
        n = len(lats)
        stats = {
            "op": op,
            "count": n,
            "throughput": round(n / elapsed, 1),
            "mean_ms": round(statistics.mean(lats), 2),
            "p50_ms":  round(lats[int(n * 0.50)], 2),
            "p95_ms":  round(lats[int(n * 0.95)], 2),
            "p99_ms":  round(lats[int(n * 0.99)], 2),
            "max_ms":  round(lats[-1], 2),
            "errors":  self.errors,
        }
        print(f"\n{'─'*52}")
        print(f"  {op} RESULTS  [{CONFIG_TAG.upper()}]")
        print(f"  Total ops    : {stats['count']:,}")
        print(f"  Throughput   : {stats['throughput']:,.0f} ops/sec")
        print(f"  Mean latency : {stats['mean_ms']} ms")
        print(f"  p50 latency  : {stats['p50_ms']} ms")
        print(f"  p95 latency  : {stats['p95_ms']} ms")
        print(f"  p99 latency  : {stats['p99_ms']} ms")
        print(f"  Max latency  : {stats['max_ms']} ms")
        print(f"  Errors       : {stats['errors']}")
        print(f"{'─'*52}\n")
        return stats

    # ── SAVE CSV ────────────────────────────────────────────────
    def _save_results(self, op, stats):
        os.makedirs("results", exist_ok=True)
        fname = f"results/{CONFIG_TAG}_{op.lower()}_results.csv"
        write_header = not os.path.exists(fname)
        with open(fname, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(stats.keys()) + ["timestamp"])
            if write_header:
                writer.writeheader()
            stats["timestamp"] = datetime.now().isoformat()
            writer.writerow(stats)
        print(f"  💾 Results saved → {fname}")

    # ── PLOT LATENCIES ──────────────────────────────────────────
    def plot_latencies(self):
        fig = plt.figure(figsize=(16, 10), facecolor="#0a0c10")
        gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.45, wspace=0.35)

        datasets = [
            (self.write_latencies, "Write Latency Distribution", "#00d4ff"),
            (self.read_latencies,  "Read Latency Distribution",  "#7fff6b"),
        ]

        for idx, (data, title, color) in enumerate(datasets):
            if not data:
                continue
            ax = fig.add_subplot(gs[0, idx])
            ax.set_facecolor("#0f1318")
            ax.hist(data, bins=80, color=color, alpha=0.8, edgecolor="none")
            ax.set_title(title, color="#e2ecf4", pad=10, fontsize=11)
            ax.set_xlabel("Latency (ms)", color="#5a7a96", fontsize=9)
            ax.set_ylabel("Frequency", color="#5a7a96", fontsize=9)
            ax.tick_params(colors="#5a7a96")
            for spine in ax.spines.values():
                spine.set_color("#1e2a38")

            # Percentile lines
            lats = sorted(data)
            n = len(lats)
            for pct, label, lc in [
                (0.50, "p50", "#ffd700"),
                (0.95, "p95", "#ff6b35"),
                (0.99, "p99", "#ff3366"),
            ]:
                val = lats[int(n * pct)]
                ax.axvline(val, color=lc, linestyle="--", linewidth=1.2, alpha=0.8)
                ax.text(val, ax.get_ylim()[1] * 0.9, f" {label}", color=lc, fontsize=8)

        # Throughput comparison bar chart
        ax3 = fig.add_subplot(gs[1, :])
        ax3.set_facecolor("#0f1318")
        ops   = ["Write Ops/sec", "Read Ops/sec"]
        vals  = [
            len(self.write_latencies) / max(1, sum(self.write_latencies) / 1000),
            len(self.read_latencies)  / max(1, sum(self.read_latencies) / 1000),
        ]
        bars = ax3.bar(ops, vals, color=["#00d4ff", "#7fff6b"], width=0.4, alpha=0.85)
        for bar, val in zip(bars, vals):
            ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 50,
                     f"{val:,.0f}", ha="center", color="#e2ecf4", fontsize=12, fontweight="bold")
        ax3.set_title(f"Throughput — {CONFIG_TAG.capitalize()} Config", color="#e2ecf4", pad=10, fontsize=11)
        ax3.tick_params(colors="#5a7a96")
        ax3.set_facecolor("#0f1318")
        for spine in ax3.spines.values():
            spine.set_color("#1e2a38")

        fig.suptitle(f"Cassandra Stress Test Results [{CONFIG_TAG.upper()}]",
                     color="#00d4ff", fontsize=14, fontweight="bold", y=0.98)

        os.makedirs("results", exist_ok=True)
        out = f"results/{CONFIG_TAG}_latency_charts.png"
        plt.savefig(out, dpi=150, bbox_inches="tight", facecolor="#0a0c10")
        print(f"  📊 Chart saved → {out}")

    def close(self):
        self.cluster.shutdown()
        print("🔌 Connection closed.")


# ── ENTRY POINT ─────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cassandra Stress Test")
    parser.add_argument("--mode", choices=["write", "read", "both"], default="both",
                        help="Test mode: write, read, or both (default: both)")
    args = parser.parse_args()

    test = CassandraStressTest()
    try:
        if args.mode in ("write", "both"):
            test.run_write_stress()
        if args.mode in ("read", "both"):
            test.run_read_stress()
        test.plot_latencies()
    finally:
        test.close()
