set dotenv-load := true

# 📊 Benchmark configuration (optimized for stable peak throughput)
BENCH_DURATION   := "300"   # 5 min → smooths out transient spikes
BENCH_CLIENTS    := "20"    # Adjust to match your CPU core count
BENCH_JOBS       := "20"    # MUST equal clients for 1:1 thread:connection mapping
BENCH_SCALE      := "50"    # Larger dataset prevents trivial RAM-cache artifacts

# 🛠️ Lifecycle
up:
    docker compose up -d postgres postgres-exporter prometheus grafana

down:
    docker compose down

clean:
    docker compose down -v

# 🗄️ Initialization
bench-init:
    @echo "📦 Initializing benchmark database (scale={{BENCH_SCALE}})..."
    docker compose run --rm --no-deps pgbench pgbench -i -s {{BENCH_SCALE}} -U $POSTGRES_USER -d $POSTGRES_DB
    docker compose run --rm --no-deps pgbench psql -U $POSTGRES_USER -d $POSTGRES_DB -c "CREATE EXTENSION IF NOT EXISTS pg_stat_statements;"

# ⏱️ Stable max-throughput benchmark (no rate cap, no manual warmup)
bench-run duration=BENCH_DURATION clients=BENCH_CLIENTS jobs=BENCH_JOBS:
    @echo "🚀 pgbench: {{duration}}s | {{clients}} clients | {{jobs}} threads (MAX THROUGHPUT)"
    docker compose run --rm --no-deps pgbench pgbench \
      -c {{clients}} -j {{jobs}} -T {{duration}} -M prepared \
      -P 10 -r \
      -U $POSTGRES_USER -d $POSTGRES_DB

# 🔧 Config reload
reload:
    @echo "🔄 Reloading PostgreSQL configuration..."
    docker compose exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT pg_reload_conf();"

restart:
    docker compose restart postgres

logs:
    docker compose logs -f

status:
    docker compose ps