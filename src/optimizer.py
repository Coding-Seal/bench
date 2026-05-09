import logging
import time

import optuna
import optunahub

from .benchmark_runner import run_benchmark
from .config import BENCH_DURATION, STORAGE_URL, STUDY_NAME
from .metrics_client import poll_prometheus_metrics
from .pg_manager import (
    apply_config,
    backup_config,
    reload_or_restart,
    restore_config,
    wait_for_postgres,
)
from .search_space import SEARCH_SPACE, config_to_pg, suggest_from_trial

logger = logging.getLogger(__name__)


# ── Shared trial logic ────────────────────────────────────────────────────────

def _run_trial(pg_params: dict, trial_id: int | str) -> float:
    """
    Apply pg_params, benchmark, return TPS.
    Restores config and restarts Postgres on any failure before re-raising.
    """
    logger.info("Trial %s | %s", trial_id, pg_params)
    backup_config()
    try:
        needs_restart = apply_config(pg_params)
        reload_or_restart(needs_restart)
        time.sleep(5)
        start_ts, end_ts = run_benchmark(duration=BENCH_DURATION)
        time.sleep(15)  # wait for Prometheus to complete at least one scrape after benchmark
        metrics = poll_prometheus_metrics(start_ts, end_ts)
        logger.info("  TPS=%.2f | Cache Hit=%.1f%%", metrics["avg_tps"], metrics["cache_hit_ratio"])
        return metrics["avg_tps"]
    except BaseException:
        restore_config()
        reload_or_restart(needs_restart=True)
        wait_for_postgres()
        raise


# ── Objective ─────────────────────────────────────────────────────────────────

def _objective(trial: optuna.Trial) -> float:
    raw = suggest_from_trial(trial)
    pg_params = config_to_pg(raw)
    trial.set_user_attr("pg_config", pg_params)
    try:
        return _run_trial(pg_params, trial.number)
    except Exception as e:
        logger.warning("Trial %s failed: %s", trial.number, e)
        # TrialPruned causes SMACSampler.after_trial to assert values is not None.
        # Return a worst-case value so SMAC can still update its model.
        return 0.0 if trial.study.direction == optuna.study.StudyDirection.MAXIMIZE else float("inf")


# ── Sampler selection ─────────────────────────────────────────────────────────

def _build_sampler(sampler: str) -> optuna.samplers.BaseSampler:
    if sampler == "smac":
        try:
            module = optunahub.load_module("samplers/smac_sampler")
            logger.info("Using SMAC sampler")
            return module.SMACSampler(search_space=SEARCH_SPACE)
        except Exception as e:
            logger.warning("SMAC sampler unavailable (%s), falling back to TPE", e)
    logger.info("Using TPE sampler")
    return optuna.samplers.TPESampler(seed=42)


# ── Runner ────────────────────────────────────────────────────────────────────

def run_optimization(trials: int, direction: str, sampler: str = "smac") -> None:
    logger.info("Starting PostgreSQL Optimization (%s) — %d trials", sampler.upper(), trials)
    logger.info("Storage: %s | Study: %s", STORAGE_URL, STUDY_NAME)

    study = optuna.create_study(
        storage=STORAGE_URL,
        study_name=STUDY_NAME,
        direction=direction,
        sampler=_build_sampler(sampler),
        load_if_exists=True,
    )

    def _stop_when_done(study: optuna.Study, _) -> None:
        n_done = len(study.get_trials(states=[optuna.trial.TrialState.COMPLETE]))
        if n_done >= trials:
            study.stop()

    try:
        study.optimize(_objective, callbacks=[_stop_when_done])
    except KeyboardInterrupt:
        logger.warning("Interrupted — stopping after current trial")
    finally:
        try:
            logger.info("Best TPS:    %.2f", study.best_value)
            logger.info("Best Config: %s", study.best_params)
        except ValueError:
            logger.info("No trials completed successfully")
        logger.info("Visualize: optuna-dashboard %s", STORAGE_URL)
