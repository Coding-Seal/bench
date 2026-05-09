import optuna
from optuna.distributions import (
    CategoricalDistribution,
    FloatDistribution,
    IntDistribution,
)

# Single source of truth for parameter bounds.
# Parallel-worker hierarchy is enforced by clipping in config_to_pg, not by
# dynamic bounds, so both SMAC and TPE operate on the same fixed space.
SEARCH_SPACE: dict[str, IntDistribution | FloatDistribution | CategoricalDistribution] = {
    "shared_buffers_mb":               IntDistribution(512,  2048, step=256),
    "work_mem_kb":                     IntDistribution(2048, 12288, step=512),
    "maintenance_work_mem_mb":         IntDistribution(128,    512, step=64),
    "effective_cache_size_gb":         IntDistribution(2,        4),
    "huge_pages":                      CategoricalDistribution(["off", "try"]),
    "wal_buffers_mb":                  IntDistribution(16,      64, step=16),
    "checkpoint_timeout_min":          IntDistribution(5,       30, step=5),
    "max_wal_size_gb":                 IntDistribution(4,       16, step=2),
    "min_wal_size_gb":                 IntDistribution(1,        5),
    "checkpoint_completion_target":    FloatDistribution(0.7,  0.95, step=0.05),
    "random_page_cost":                FloatDistribution(1.0,   4.0, step=0.1),
    "effective_io_concurrency":        IntDistribution(100,    400, step=50),
    "default_statistics_target":       IntDistribution(50,     500, step=25),
    "max_connections":                 IntDistribution(25,     400, step=25),
    "max_worker_processes":            IntDistribution(2,       8),
    "max_parallel_workers":            IntDistribution(2,       8),
    "max_parallel_workers_per_gather": IntDistribution(0,       8),
    "max_parallel_maintenance_workers":IntDistribution(1,       8),
}


# pgTune baselines: PostgreSQL 17, 4 GB RAM, 4 CPUs, SSD.
# Values are in search-space units (raw, before config_to_pg).
_Baseline = dict[str, int | float | str]

PGTUNE_BASELINES: dict[str, _Baseline] = {
    "oltp": {
        "shared_buffers_mb":                1024,
        "work_mem_kb":                      4096,  # 4 MB
        "maintenance_work_mem_mb":           256,
        "effective_cache_size_gb":             3,
        "huge_pages":                       "off",
        "wal_buffers_mb":                     16,
        "checkpoint_timeout_min":              5,
        "max_wal_size_gb":                     8,
        "min_wal_size_gb":                     2,
        "checkpoint_completion_target":      0.9,
        "random_page_cost":                  1.1,
        "effective_io_concurrency":          200,
        "default_statistics_target":         100,
        "max_connections":                   300,
        "max_worker_processes":                4,
        "max_parallel_workers":                4,
        "max_parallel_workers_per_gather":     2,
        "max_parallel_maintenance_workers":    2,
    },
    "olap": {
        "shared_buffers_mb":                1024,
        "work_mem_kb":                     10752,  # pgTune: 10723 kB → nearest step=512
        "maintenance_work_mem_mb":           512,
        "effective_cache_size_gb":             3,
        "huge_pages":                       "off",
        "wal_buffers_mb":                     16,
        "checkpoint_timeout_min":              5,
        "max_wal_size_gb":                    16,
        "min_wal_size_gb":                     4,
        "checkpoint_completion_target":      0.9,
        "random_page_cost":                  4.0,
        "effective_io_concurrency":          200,
        "default_statistics_target":         500,
        "max_connections":                    50,  # pgTune: 40 → nearest step=25
        "max_worker_processes":                4,
        "max_parallel_workers":                4,
        "max_parallel_workers_per_gather":     2,
        "max_parallel_maintenance_workers":    2,
    },
}


def suggest_from_trial(trial: optuna.Trial) -> dict:
    result = {}
    for name, dist in SEARCH_SPACE.items():
        if isinstance(dist, CategoricalDistribution):
            result[name] = trial.suggest_categorical(name, list(dist.choices))
        elif isinstance(dist, IntDistribution):
            result[name] = trial.suggest_int(name, dist.low, dist.high, step=dist.step)
        elif isinstance(dist, FloatDistribution):
            result[name] = trial.suggest_float(name, dist.low, dist.high, step=dist.step)
    return result


def _snap_int(value: float, step: int) -> int:
    return int(round(value / step) * step)


def _snap_float(value: float, step: float, decimals: int) -> float:
    return round(round(value / step) * step, decimals)


def config_to_pg(raw: dict) -> dict:
    """
    Convert a raw config dict to PostgreSQL parameter strings.
    Snaps values to their step grid and clips the parallel-worker hierarchy.
    """
    mwp  = int(raw["max_worker_processes"])
    pw   = min(int(raw["max_parallel_workers"]), mwp)
    pwpg = min(int(raw["max_parallel_workers_per_gather"]), pw)
    pmw  = min(int(raw["max_parallel_maintenance_workers"]), mwp)

    return {
        "shared_buffers":               f"{_snap_int(raw['shared_buffers_mb'], 256)}MB",
        "work_mem":                     f"{_snap_int(raw['work_mem_kb'], 512)}kB",
        "maintenance_work_mem":         f"{_snap_int(raw['maintenance_work_mem_mb'], 64)}MB",
        "effective_cache_size":         f"{int(raw['effective_cache_size_gb'])}GB",
        "huge_pages":                   raw["huge_pages"],
        "wal_buffers":                  f"{_snap_int(raw['wal_buffers_mb'], 16)}MB",
        "checkpoint_timeout":           f"{_snap_int(raw['checkpoint_timeout_min'], 5)}min",
        "max_wal_size":                 f"{_snap_int(raw['max_wal_size_gb'], 2)}GB",
        "min_wal_size":                 f"{int(raw['min_wal_size_gb'])}GB",
        "checkpoint_completion_target": _snap_float(raw["checkpoint_completion_target"], 0.05, 2),
        "random_page_cost":             _snap_float(raw["random_page_cost"], 0.1, 1),
        "effective_io_concurrency":     _snap_int(raw["effective_io_concurrency"], 50),
        "default_statistics_target":    _snap_int(raw["default_statistics_target"], 25),
        "max_connections":              _snap_int(raw["max_connections"], 25),
        "max_worker_processes":         mwp,
        "max_parallel_workers":         pw,
        "max_parallel_workers_per_gather":   pwpg,
        "max_parallel_maintenance_workers":  pmw,
    }
