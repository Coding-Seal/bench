import pytest
from optuna.distributions import CategoricalDistribution, FloatDistribution, IntDistribution

from src.search_space import (
    PGTUNE_BASELINES,
    SEARCH_SPACE,
    _snap_float,
    _snap_int,
    config_to_pg,
)


def _base_raw() -> dict:
    return {
        "shared_buffers_mb": 512,
        "work_mem_kb": 2048,
        "maintenance_work_mem_mb": 128,
        "effective_cache_size_gb": 2.0,
        "huge_pages": "off",
        "wal_buffers_mb": 16,
        "checkpoint_timeout_min": 5,
        "max_wal_size_gb": 4,
        "min_wal_size_gb": 2,
        "checkpoint_completion_target": 0.9,
        "wal_compression": "lz4",
        "random_page_cost": 1.1,
        "seq_page_cost": 1.0,
        "effective_io_concurrency": 200,
        "default_statistics_target": 100,
        "jit": "off",
        "temp_buffers_mb": 8,
        "bgwriter_lru_maxpages": 100,
        "bgwriter_delay_ms": 200,
        "max_connections": 100,
        "max_worker_processes": 4,
        "max_parallel_workers": 4,
        "max_parallel_workers_per_gather": 2,
        "max_parallel_maintenance_workers": 2,
    }


# ── _snap_int ─────────────────────────────────────────────────────────────────


def test_snap_int_exact():
    assert _snap_int(256, 256) == 256


def test_snap_int_rounds_down():
    assert _snap_int(300, 256) == 256  # 300/256=1.17 → rounds to 1


def test_snap_int_rounds_up():
    assert _snap_int(400, 256) == 512  # 400/256=1.56 → rounds to 2


# ── _snap_float ───────────────────────────────────────────────────────────────


def test_snap_float_exact():
    assert _snap_float(0.9, 0.05, 2) == pytest.approx(0.9)


def test_snap_float_rounds():
    assert _snap_float(0.92, 0.05, 2) == pytest.approx(0.90)


def test_snap_float_rounds_up():
    assert _snap_float(0.94, 0.05, 2) == pytest.approx(0.95)


# ── config_to_pg: output units ────────────────────────────────────────────────


def test_output_units():
    pg = config_to_pg(_base_raw())
    assert pg["shared_buffers"] == "512MB"
    assert pg["work_mem"] == "2048kB"
    assert pg["maintenance_work_mem"] == "128MB"
    assert pg["wal_buffers"] == "16MB"
    assert pg["checkpoint_timeout"] == "5min"
    assert pg["bgwriter_delay"] == "200ms"


def test_effective_cache_size_converted_to_mb():
    raw = _base_raw()
    raw["effective_cache_size_gb"] = 3.5
    assert config_to_pg(raw)["effective_cache_size"] == "3584MB"


def test_effective_cache_size_integer_gb():
    raw = _base_raw()
    raw["effective_cache_size_gb"] = 2.0
    assert config_to_pg(raw)["effective_cache_size"] == "2048MB"


# ── config_to_pg: parallel-worker hierarchy ───────────────────────────────────


def test_parallel_workers_clipped_to_worker_processes():
    raw = _base_raw()
    raw["max_worker_processes"] = 3
    raw["max_parallel_workers"] = 8
    pg = config_to_pg(raw)
    assert pg["max_parallel_workers"] == 3


def test_per_gather_clipped_to_parallel_workers():
    raw = _base_raw()
    raw["max_worker_processes"] = 8
    raw["max_parallel_workers"] = 4
    raw["max_parallel_workers_per_gather"] = 6
    pg = config_to_pg(raw)
    assert pg["max_parallel_workers_per_gather"] == 4


def test_maintenance_workers_clipped_to_worker_processes():
    raw = _base_raw()
    raw["max_worker_processes"] = 3
    raw["max_parallel_maintenance_workers"] = 8
    pg = config_to_pg(raw)
    assert pg["max_parallel_maintenance_workers"] == 3


def test_all_parallel_within_bounds_unchanged():
    raw = _base_raw()
    pg = config_to_pg(raw)
    assert pg["max_worker_processes"] == 4
    assert pg["max_parallel_workers"] == 4
    assert pg["max_parallel_workers_per_gather"] == 2
    assert pg["max_parallel_maintenance_workers"] == 2


# ── config_to_pg: min_wal ≤ max_wal ──────────────────────────────────────────


def test_min_wal_capped_to_max_wal():
    raw = _base_raw()
    raw["max_wal_size_gb"] = 4
    raw["min_wal_size_gb"] = 10
    pg = config_to_pg(raw)
    assert pg["min_wal_size"] == "4GB"


def test_min_wal_within_max_wal_unchanged():
    raw = _base_raw()
    raw["max_wal_size_gb"] = 8
    raw["min_wal_size_gb"] = 2
    pg = config_to_pg(raw)
    assert pg["min_wal_size"] == "2GB"
    assert pg["max_wal_size"] == "8GB"


# ── PGTUNE_BASELINES within SEARCH_SPACE ─────────────────────────────────────


@pytest.mark.parametrize("workload", ["oltp", "olap"])
def test_baseline_values_within_search_space(workload):
    baseline = PGTUNE_BASELINES[workload]
    for name, value in baseline.items():
        dist = SEARCH_SPACE[name]
        if isinstance(dist, CategoricalDistribution):
            assert value in dist.choices, f"{workload}.{name}={value!r} not in {list(dist.choices)}"
        elif isinstance(dist, IntDistribution):
            assert dist.low <= int(value) <= dist.high, (
                f"{workload}.{name}={value} out of [{dist.low}, {dist.high}]"
            )
        elif isinstance(dist, FloatDistribution):
            assert dist.low <= float(value) <= dist.high, (
                f"{workload}.{name}={value} out of [{dist.low}, {dist.high}]"
            )


@pytest.mark.parametrize("workload", ["oltp", "olap"])
def test_baseline_covers_all_search_space_keys(workload):
    assert set(PGTUNE_BASELINES[workload].keys()) == set(SEARCH_SPACE.keys())
