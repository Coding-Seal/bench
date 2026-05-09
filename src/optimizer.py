# src/optimizer.py
import optuna
import csv
import time
import sys
from .pg_manager import backup_config, restore_config, apply_config, reload_or_restart, wait_for_postgres
from .benchmark_runner import run_benchmark
from .metrics_client import poll_prometheus_metrics
from .config import STORAGE_URL, STUDY_NAME
import optuna
import optunahub

def objective(trial: optuna.Trial) -> float:
    """
    PostgreSQL configuration objective using pgTune-style parameters.
    Search ranges are centered around pgTune recommendations for a 4GB RAM, 
    SSD-backed, OLTP workload.
    """
    # 🔧 pgTune-style parameter space
    config = {}

    # === MEMORY (Independent) ===
    config["shared_buffers"] = f"{trial.suggest_int('shared_buffers_mb', 512, 2048, step=256)}MB"
    config["work_mem"] = f"{trial.suggest_int('work_mem_kb', 2048, 8192, step=512)}kB"
    config["maintenance_work_mem"] = f"{trial.suggest_int('maintenance_work_mem_mb', 128, 512, step=64)}MB"
    config["effective_cache_size"] = f"{trial.suggest_int('effective_cache_size_gb', 2, 4)}GB"
    config["huge_pages"] = trial.suggest_categorical("huge_pages", ["off", "try"])

    # === WAL & CHECKPOINTS (Independent) ===
    config["wal_buffers"] = f"{trial.suggest_int('wal_buffers_mb', 16, 64, step=16)}MB"
    config["checkpoint_timeout"] = f"{trial.suggest_int('checkpoint_timeout_min', 5, 30, step=5)}min"
    config["max_wal_size"] = f"{trial.suggest_int('max_wal_size_gb', 4, 12, step=2)}GB"
    config["min_wal_size"] = f"{trial.suggest_int('min_wal_size_gb', 1, 5)}GB"
    config["checkpoint_completion_target"] = trial.suggest_float("checkpoint_completion_target", 0.7, 0.95, step=0.05)

    # === PLANNER & SSD (Independent) ===
    config["random_page_cost"] = trial.suggest_float("random_page_cost", 1.0, 2.0, step=0.1)
    config["effective_io_concurrency"] = trial.suggest_int("effective_io_concurrency", 100, 400, step=50)
    config["default_statistics_target"] = trial.suggest_int("default_statistics_target", 50, 200, step=25)

    # === CONNECTIONS & PARALLELISM (Enforced Interdependencies) ===
    config["max_connections"] = trial.suggest_int("max_connections", 100, 400, step=25)

    # 1. Sample the root constraint first
    max_wp = trial.suggest_int("max_worker_processes", 2, 8)
    config["max_worker_processes"] = max_wp

    # 2. max_parallel_workers <= max_worker_processes
    max_pw = trial.suggest_int("max_parallel_workers", 2, max_wp)
    config["max_parallel_workers"] = max_pw

    # 3. max_parallel_workers_per_gather <= max_parallel_workers
    max_pwpg = trial.suggest_int("max_parallel_workers_per_gather", 0, max_pw)
    config["max_parallel_workers_per_gather"] = max_pwpg

    # 4. max_parallel_maintenance_workers <= max_worker_processes
    max_pmw = trial.suggest_int("max_parallel_maintenance_workers", 1, max_wp)
    config["max_parallel_maintenance_workers"] = max_pmw

    trial.set_user_attr("config", config)
    print(f"🔧 Trial {trial.number} | Config: {config}")

    try:
        backup_config()
        needs_restart = apply_config(config)
        reload_or_restart(needs_restart)

        time.sleep(5)  # Allow cache stabilization after config change
        start_ts, end_ts = run_benchmark(duration=300)
        metrics = poll_prometheus_metrics(start_ts, end_ts)
        print(f"📊 Result: TPS={metrics['avg_tps']:.2f} | Cache Hit={metrics['cache_hit_ratio']:.1f}%")

        return metrics["avg_tps"]

    except Exception as e:
        print(f"❌ Trial {trial.number} failed: {e}")
        restore_config()
        wait_for_postgres()
        raise optuna.exceptions.TrialPruned()
    

def run_optimization(trials: int = 20, direction: str = "maximize"):
    print("🚀 Starting PostgreSQL Optimization Loop (SMAC)...")
    print(f"💾 Storage: {STORAGE_URL}")
    print(f"📖 Study: {STUDY_NAME}")

    try:
        module = optunahub.load_module("samplers/smac_sampler")
        sampler = module.SMACSampler()
        print("✅ Using SMAC Bayesian optimizer")
    except ImportError:
        print("⚠️ SMAC not installed. Falling back to TPE sampler. Run: pip install smac")
        from optuna.samplers import TPESampler
        sampler = TPESampler(seed=42)

    study = optuna.create_study(
        storage=STORAGE_URL,
        study_name=STUDY_NAME,
        direction=direction,
        sampler=sampler,
        load_if_exists=True
    )

    def callback(study, trial):
        n_complete = len(study.get_trials(states=[optuna.trial.TrialState.COMPLETE]))
        if n_complete >= trials:
            study.stop()

    

    study.optimize(objective, callbacks=[callback])

    print("\n✅ Optimization Complete!")
    if study.best_trial is not None:
        print(f"🏆 Best TPS: {study.best_value:.2f}")
        print(f"⚙️ Best Config: {study.best_params}")
    else:
        print("⚠️ No trials completed successfully.")

    print(f"\n📊 Visualize results with:")
    print(f"   optuna-dashboard {STORAGE_URL}")