# PostgreSQL Configuration Optimizer

Bayesian optimization of PostgreSQL knobs using Optuna (SMAC / TPE samplers) with pgbench as the workload driver and Prometheus for metric collection.

## Architecture

```
main.py
  └─ src/optimizer.py        # Optuna study, objective, warmup, pgTune baseline
       ├─ src/search_space.py     # SEARCH_SPACE distributions, PGTUNE_BASELINES, config_to_pg
       ├─ src/pg_manager.py       # Edit performance.conf, docker restart/reload
       ├─ src/benchmark_runner.py # Run pgbench via docker compose
       ├─ src/metrics_client.py   # Query Prometheus for TPS, latency, cache hit
       └─ src/config.py           # Paths, env vars, restart-required param set
```

## Infrastructure (Docker Compose)

| Service            | Port  | Role                                      |
|--------------------|-------|-------------------------------------------|
| `postgres`         | 5432  | PostgreSQL 17, CPU-pinned to cores 2-5, 4 GB RAM |
| `pgbench`          | —     | One-shot benchmark runner (ephemeral)     |
| `postgres-exporter`| 9187  | pg_stat_* → Prometheus                   |
| `prometheus`       | 9090  | Metrics storage (10 s scrape interval)   |
| `grafana`          | 3000  | Dashboards                                |

## Config files

- `postgresql/config/postgresql.conf` — base config; loads `performance.conf` via `include`
- `postgresql/config/performance.conf` — **the file the optimizer writes** (tunable knobs only)
- `postgresql/config/performance.conf.bak` — auto-backup before each trial

## Parameter space (`src/search_space.py`)

Single source of truth: `SEARCH_SPACE` dict of Optuna distributions. Parallel-worker hierarchy is enforced by clipping in `config_to_pg`, not by dynamic bounds, so SMAC and TPE both operate on the same fixed space.

### Memory
- `shared_buffers` 512–2048 MB (step 256)
- `work_mem` 2048–12288 kB (step 512)
- `maintenance_work_mem` 128–512 MB (step 64)
- `effective_cache_size` 2–4 GB
- `huge_pages` off | try

### WAL & Checkpoints
- `wal_buffers` 16–64 MB (step 16)
- `checkpoint_timeout` 5–30 min (step 5)
- `max_wal_size` 4–16 GB (step 2)
- `min_wal_size` 1–5 GB
- `checkpoint_completion_target` 0.7–0.95 (step 0.05)

### Planner / I/O
- `random_page_cost` 1.0–4.0 (step 0.1)
- `effective_io_concurrency` 100–400 (step 50)
- `default_statistics_target` 50–500 (step 25)

### Connections & Parallelism (interdependent)
- `max_connections` 25–400 (step 25)
- `max_worker_processes` 2–8 (root constraint)
- `max_parallel_workers` 2–8, clipped to max_worker_processes
- `max_parallel_workers_per_gather` 0–8, clipped to max_parallel_workers
- `max_parallel_maintenance_workers` 1–8, clipped to max_worker_processes

### Restart-required params (full docker restart, not just pg_reload_conf)
`shared_buffers`, `max_connections`, `huge_pages`, `wal_level`, `max_worker_processes`,
`max_parallel_workers`, `max_parallel_workers_per_gather`, `max_parallel_maintenance_workers`

## Optimization objective

Configurable via `--objective` (or `OBJECTIVE` env var):
- `tps` — maximize `pg_stat_database_xact_commit` rate (default)
- `latency` — minimize `active_time_seconds_total / xact_commit * 1000` (ms)

Both metrics plus cache hit ratio are stored as trial user attributes. Study direction is derived automatically from the objective.

## Samplers

1. **SMAC** (`optunahub` `samplers/smac_sampler`) — primary
2. **TPE** (`optuna.samplers.TPESampler`, seed=42) — fallback when SMAC unavailable

Study persists in `optuna_study.db` (SQLite). `load_if_exists=True` so runs are resumable via `--continue`.

## Common commands (justfile)

```bash
just up            # Start postgres + monitoring stack
just db-init       # pgbench -i -s 50 + CREATE EXTENSION pg_stat_statements
just bench         # Manual one-shot benchmark
just reload        # pg_reload_conf() without restart
just restart       # docker compose restart postgres
just logs          # Follow all logs
just status        # docker compose ps
just down          # Stop everything
just clean         # Stop + remove volumes
just dashboard     # Open optuna-dashboard for optuna_study.db
```

## Running the optimizer

```bash
uv sync

# Default: 20 trials, SMAC, OLTP workload, minimize latency
just optimize

# Custom
uv run python main.py --trials 50 --sampler tpe --workload olap --objective tps --duration 60

# Resume a previous study
uv run python main.py --continue pg_olap_tps_smac_2026-05-09-14:30:22
```

Study names are auto-generated as `pg_{workload}_{objective}_{sampler}_{timestamp}`.

## Environment variables (.env)

| Variable              | Default                  | Purpose                        |
|-----------------------|--------------------------|--------------------------------|
| `POSTGRES_USER`       | postgres                 | DB user                        |
| `POSTGRES_PASSWORD`   | —                        | DB password                    |
| `POSTGRES_DB`         | postgres                 | Database name                  |
| `PROMETHEUS_URL`      | http://localhost:9090    | Prometheus endpoint            |
| `PG_CONFIG_FILE`      | performance.conf         | Config filename to tune        |
| `OPTUNA_STUDY_NAME`   | pg_config_optimization   | Override auto-generated name   |
| `BENCH_DURATION`      | 30                       | pgbench seconds per trial      |
| `BENCH_TRIM`          | 0.025                    | Fraction trimmed from each end of Prometheus window |
| `WORKLOAD`            | oltp                     | oltp \| olap                   |
| `OBJECTIVE`           | tps                      | tps \| latency                 |
| `GRAFANA_ADMIN_USER`  | —                        | Grafana login                  |
| `GRAFANA_ADMIN_PASSWORD` | —                     | Grafana password               |

## Trial flow

1. **Warmup** — one full benchmark run before trial 0 to prime shared_buffers (results discarded)
2. **pgTune baseline** — workload-specific starting config injected via `study.add_trial()` (bypasses SMAC's `after_trial` to avoid seed-tracking assertion)
3. For each Optuna trial:
   1. `backup_config()` — copy performance.conf → .bak
   2. `apply_config(params)` — regex-patch performance.conf; append missing keys
   3. `reload_or_restart(needs_restart)` — full restart if any restart-required param changed, else `pg_reload_conf()`
   4. `time.sleep(5)` — allow buffer cache to stabilize
   5. `run_benchmark(duration=BENCH_DURATION, workload=WORKLOAD)` — pgbench via docker compose
   6. `time.sleep(15)` — wait for Prometheus scrape
   7. `poll_prometheus_metrics(start + trim, end - trim)` — middle 95% of window (default) to avoid rate()[1m] bleed
   8. Return objective value; on any exception restore config and restart Postgres

## Key design decisions

- Config is edited directly on the host filesystem, mounted into the container — no `ALTER SYSTEM`, no superuser session needed.
- CPU pinning (cores 2-5) isolates Postgres from the optimizer process to reduce noise.
- pgbench scale=50 (~720 MB dataset) prevents trivial in-RAM caching from masking config effects.
- SMAC cannot handle `TrialPruned` — failed trials return worst-case value (0.0 / inf) instead.
- `subprocess.Popen` with `start_new_session=True` isolates docker from the terminal's process group; Ctrl+C sends `docker compose stop --timeout 5 pgbench` for clean shutdown.
- Prometheus window is trimmed by `BENCH_TRIM` on each side: `rate()[1m]` lookback at `start_ts` bleeds pre-benchmark traffic into the first minute of data.
- pgTune baseline is injected via `study.add_trial()` not `enqueue_trial()` — enqueuing creates a trial without SMAC seed info, breaking its intensifier on the next `ask()`.
- `optimizer.py` imports `src.config` as a module (`from . import config as cfg`) so runtime mutations in `main.py` (`cfg.WORKLOAD = ...`, etc.) are visible when trial functions execute.
