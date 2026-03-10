-- ========================================================
-- Compaction Strategy Migration Scripts
-- Switch strategies live without downtime
-- ========================================================

USE perf_test;

-- ── SWITCH sensor_events: STCS → LCS ────────────────────
-- Use when read workload increases significantly
ALTER TABLE sensor_events
WITH compaction = {
  'class': 'LeveledCompactionStrategy',
  'sstable_size_in_mb': 160
};

-- ── SWITCH sensor_events: back to STCS ──────────────────
-- Use when write throughput is the priority
ALTER TABLE sensor_events
WITH compaction = {
  'class': 'SizeTieredCompactionStrategy',
  'min_threshold': 4,
  'max_threshold': 32
};

-- ── SWITCH sensor_events to TWCS (time-series) ──────────
-- Best for data with TTL and time-based access patterns
ALTER TABLE sensor_events
WITH compaction = {
  'class': 'TimeWindowCompactionStrategy',
  'compaction_window_unit': 'HOURS',
  'compaction_window_size': 1
};

-- ── ENABLE row cache on user_profiles ───────────────────
ALTER TABLE user_profiles
WITH caching = {
  'keys': 'ALL',
  'rows_per_partition': 'NONE'
};

-- ── DISABLE row cache (e.g. during benchmarking baseline)
ALTER TABLE user_profiles
WITH caching = {
  'keys': 'ALL',
  'rows_per_partition': '0'
};
