-- ========================================================
-- Cassandra Schema — Distributed DB Performance Project
-- Run with: cqlsh -3f schema/schema.cql
-- ========================================================

-- Create keyspace with NetworkTopologyStrategy (RF=3)
CREATE KEYSPACE IF NOT EXISTS perf_test
  WITH REPLICATION = {
    'class': 'NetworkTopologyStrategy',
    'datacenter1': 2
  }
  AND DURABLE_WRITES = true;

USE perf_test;

-- ── TABLE 1: sensor_events ───────────────────────────────
-- Write-heavy workload → SizeTieredCompactionStrategy
-- TTL: 24 hours (86400 seconds)
CREATE TABLE IF NOT EXISTS sensor_events (
  device_id   UUID,
  event_time  TIMESTAMP,
  sensor_type TEXT,
  value       DOUBLE,
  metadata    MAP<TEXT, TEXT>,
  PRIMARY KEY (device_id, event_time)
) WITH CLUSTERING ORDER BY (event_time DESC)
  AND compaction = {
    'class': 'SizeTieredCompactionStrategy',
    'min_threshold': 4,
    'max_threshold': 32
  }
  AND compression = {
    'sstable_compression': 'LZ4Compressor',
    'chunk_length_in_kb': 64
  }
  AND caching = {
    'keys': 'ALL',
    'rows_per_partition': '100'
  }
  AND gc_grace_seconds = 864000
  AND speculative_retry = '99PERCENTILE';


-- ── TABLE 2: user_profiles ───────────────────────────────
-- Read-heavy workload → LeveledCompactionStrategy
-- Row cache: entire partition is cached
CREATE TABLE IF NOT EXISTS user_profiles (
  user_id    UUID PRIMARY KEY,
  username   TEXT,
  email      TEXT,
  region     TEXT,
  created_at TIMESTAMP,
  last_login TIMESTAMP,
  tags       SET<TEXT>
) WITH compaction = {
    'class': 'LeveledCompactionStrategy',
    'sstable_size_in_mb': 160,
    'tombstone_threshold': 0.2,
    'tombstone_compaction_interval': 86400
  }
  AND compression = {
    'sstable_compression': 'LZ4Compressor',
    'chunk_length_in_kb': 64
  }
  AND caching = {
    'keys': 'ALL',
    'rows_per_partition': 'NONE'
  }
  AND gc_grace_seconds = 864000
  AND speculative_retry = '99PERCENTILE';


-- ── TABLE 3: perf_metrics ────────────────────────────────
-- Storing benchmark results for comparison
CREATE TABLE IF NOT EXISTS perf_metrics (
  run_id      UUID,
  run_time    TIMESTAMP,
  op_type     TEXT,
  throughput  DOUBLE,
  p50_ms      DOUBLE,
  p95_ms      DOUBLE,
  p99_ms      DOUBLE,
  error_count INT,
  config_tag  TEXT,
  PRIMARY KEY (run_id, run_time)
) WITH CLUSTERING ORDER BY (run_time DESC)
  AND compaction = {
    'class': 'TimeWindowCompactionStrategy',
    'compaction_window_unit': 'DAYS',
    'compaction_window_size': 1
  };
