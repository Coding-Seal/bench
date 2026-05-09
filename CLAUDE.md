# PostgreSQL Configuration Optimizer

Bayesian optimization of PostgreSQL knobs using Optuna (SMAC / TPE samplers) with pgbench as the workload driver and Prometheus for metric collection.

## Architecture

```
main.py
  └─ src/optimizer.py      # Optuna study, objective function
       ├─ src/pg_manager.py      # Edit performance.conf, docker restart/reload
       ├─ src/benchmark_runner.py # Run pgbench via docker compose
       ├─ src/metrics_client.py   # Query Prometheus for TPS + cache hit
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

## Parameter space (optimizer.py objective)

### Memory
- `shared_buffers` 512–2048 MB (step 256)
- `work_mem` 2048–8192 kB (step 512)
- `maintenance_work_mem` 128–512 MB (step 64)
- `effective_cache_size` 2–4 GB
- `huge_pages` off | try

### WAL & Checkpoints
- `wal_buffers` 16–64 MB (step 16)
- `checkpoint_timeout` 5–30 min (step 5)
- `max_wal_size` 4–12 GB (step 2)
- `min_wal_size` 1–5 GB
- `checkpoint_completion_target` 0.7–0.95 (step 0.05)

### Planner / I/O
- `random_page_cost` 1.0–2.0 (step 0.1)
- `effective_io_concurrency` 100–400 (step 50)
- `default_statistics_target` 50–200 (step 25)

### Connections & Parallelism (interdependent)
- `max_connections` 100–400 (step 25)
- `max_worker_processes` 2–8 (root constraint)
- `max_parallel_workers` 2–max_worker_processes
- `max_parallel_workers_per_gather` 0–max_parallel_workers
- `max_parallel_maintenance_workers` 1–max_worker_processes

### Restart-required params (full docker restart, not just pg_reload_conf)
`shared_buffers`, `max_connections`, `huge_pages`, `wal_level`, `max_worker_processes`,
`max_parallel_workers`, `max_parallel_workers_per_gather`, `max_parallel_maintenance_workers`

## Optimization objective

Maximize **avg TPS** (`pg_stat_database_xact_commit` rate) measured by Prometheus over the pgbench window. Cache hit ratio is also captured as a user attribute but is not the primary objective.

## Samplers

1. **SMAC** (`optunahub` `samplers/smac_sampler`) — primary
2. **TPE** (`optuna.samplers.TPESampler`, seed=42) — fallback when SMAC unavailable

Study persists in `optuna_study.db` (SQLite). `load_if_exists=True` so runs are resumable.

## Common commands (justfile)

```bash
just up            # Start postgres + monitoring stack
just bench-init    # pgbench -i -s 50 + CREATE EXTENSION pg_stat_statements
just bench-run     # Manual benchmark (300 s, 20 clients, 20 threads)
just reload        # pg_reload_conf() without restart
just restart       # docker compose restart postgres
just logs          # Follow all logs
just status        # docker compose ps
just down          # Stop everything
just clean         # Stop + remove volumes
```

## Running the optimizer

```bash
# Install deps and activate venv
uv sync
source .venv/bin/activate   # or: uv run python main.py

# Default: 20 trials, maximize TPS
python main.py

# Custom
python main.py --trials 50 --direction maximize --duration 60

# Inspect results
optuna-dashboard sqlite:///optuna_study.db
```

## Environment variables (.env)

| Variable              | Default       | Purpose                          |
|-----------------------|---------------|----------------------------------|
| `POSTGRES_USER`       | postgres      | DB user                         |
| `POSTGRES_PASSWORD`   | —             | DB password                     |
| `POSTGRES_DB`         | postgres      | Database name                   |
| `PROMETHEUS_URL`      | http://localhost:9090 | Prometheus endpoint      |
| `PG_CONFIG_FILE`      | performance.conf | Config filename to tune       |
| `OPTUNA_STUDY_NAME`   | pg_config_optimization | Optuna study name        |
| `GRAFANA_ADMIN_USER`  | —             | Grafana login                   |
| `GRAFANA_ADMIN_PASSWORD` | —          | Grafana password                |

## Trial flow

1. `backup_config()` — copy performance.conf → .bak
2. `apply_config(params)` — regex-patch performance.conf in-place; append missing keys
3. `reload_or_restart(needs_restart)` — full restart if any restart-required param changed, else `pg_reload_conf()`
4. `wait_for_postgres()` — poll `pg_isready` up to 60 s
5. `time.sleep(5)` — allow buffer cache to stabilize
6. `run_benchmark(duration=300)` — pgbench (20 clients, 20 threads, prepared statements)
7. `poll_prometheus_metrics(start_ts, end_ts)` — query avg TPS + cache hit ratio
8. Return TPS; on any exception restore config and raise `TrialPruned`

## Key design decisions

- Config is edited directly on the host filesystem, mounted into the container — no pg_alter_system, no superuser session needed.
- CPU pinning (cores 2-5) isolates Postgres from the optimizer process to reduce noise.
- pgbench scale=50 (~720 MB dataset) prevents trivial in-RAM caching from masking config effects.
- Benchmark duration is hardcoded to 300 s in the objective (the `--duration` CLI arg is currently unused in `run_optimization`).
