set dotenv-load := true

BENCH_DURATION := "120"   # 2 min — smooths transient spikes
BENCH_CLIENTS  := "20"    # match pinned CPU core count
BENCH_JOBS     := "20"    # 1:1 thread:connection mapping
BENCH_SCALE    := "50"    # ~720 MB dataset, prevents trivial RAM-cache hits

TRIALS    := "60"
SAMPLER   := "smac"        # smac | tpe
WORKLOAD  := "olap"        # oltp | olap
OBJECTIVE := "tps"         # tps  | latency

# ── Infrastructure ────────────────────────────────────────────────────────────

up:
    docker compose up -d postgres postgres-exporter prometheus grafana

down:
    docker compose down

clean:
    docker compose down -v

logs:
    docker compose logs -f

status:
    docker compose ps

# ── Database init ─────────────────────────────────────────────────────────────

# Initialize pgbench schema and enable pg_stat_statements
db-init:
    docker compose run --rm --no-deps pgbench \
      pgbench -i -s {{BENCH_SCALE}} -U $POSTGRES_USER -d $POSTGRES_DB
    docker compose run --rm --no-deps pgbench \
      psql -U $POSTGRES_USER -d $POSTGRES_DB \
      -c "CREATE EXTENSION IF NOT EXISTS pg_stat_statements;"

# ── Manual benchmark ──────────────────────────────────────────────────────────

# Run a one-shot pgbench (max throughput, no rate cap)
bench duration=BENCH_DURATION clients=BENCH_CLIENTS jobs=BENCH_JOBS:
    docker compose run --rm --no-deps pgbench pgbench \
      -c {{clients}} -j {{jobs}} -T {{duration}} -M prepared \
      -P 10 -r \
      -U $POSTGRES_USER -d $POSTGRES_DB

# ── Optimizer ─────────────────────────────────────────────────────────────────

# Run the optimizer (default: SMAC, 20 trials, 1800 s each)
optimize trials=TRIALS sampler=SAMPLER duration=BENCH_DURATION workload=WORKLOAD objective=OBJECTIVE:
    uv run python main.py --trials {{trials}} --sampler {{sampler}} --duration {{duration}} --workload {{workload}} --objective {{objective}}

# Open the Optuna dashboard (TPE runs)
dashboard:
    xdg-open http://127.0.0.1:8080
    uv run optuna-dashboard sqlite:///optuna_study.db

# ── PostgreSQL config ─────────────────────────────────────────────────────────

reload:
    docker compose exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB \
      -c "SELECT pg_reload_conf();"

restart:
    docker compose restart postgres

# ── Python env ────────────────────────────────────────────────────────────────

sync:
    uv sync --dev
    git config core.hooksPath .githooks

test:
    uv run pytest tests/ -v

fmt:
    uv run ruff format src/ tests/ main.py

lint:
    uv run ruff check src/ tests/ main.py

# ── Thesis ────────────────────────────────────────────────────────────────────

thesis:
    typst compile thesis/main.typ thesis/thesis.pdf

thesis-watch:
    typst watch thesis/main.typ thesis/thesis.pdf
