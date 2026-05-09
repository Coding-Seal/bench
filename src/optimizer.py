import logging
import time

import optuna
import optunahub

from . import config as cfg
from .benchmark_runner import run_benchmark
from .metrics_client import poll_prometheus_metrics
from .pg_manager import (
    apply_config,
    backup_config,
    reload_or_restart,
    restore_config,
    wait_for_postgres,
)
from .search_space import PGTUNE_BASELINES, SEARCH_SPACE, config_to_pg, suggest_from_trial

logger = logging.getLogger(__name__)


# ── Shared trial logic ────────────────────────────────────────────────────────

def _run_trial(pg_params: dict, trial_id: int | str) -> dict:
    """
    Apply pg_params, benchmark, return metrics dict.
    Restores config and restarts Postgres on any failure before re-raising.
    """
    logger.info("Trial %s | %s", trial_id, pg_params)
    backup_config()
    try:
        needs_restart = apply_config(pg_params)
        reload_or_restart(needs_restart)
        time.sleep(5)
        start_ts, end_ts = run_benchmark(duration=cfg.BENCH_DURATION, workload=cfg.WORKLOAD)
        time.sleep(15)  # wait for Prometheus to complete at least one scrape after benchmark
        duration = end_ts - start_ts
        trim = int(duration * cfg.BENCH_TRIM)
        prom = poll_prometheus_metrics(start_ts + trim, end_ts - trim)
        logger.info("  TPS=%.2f | Latency=%.2f ms | Cache Hit=%.1f%%",
                    prom["avg_tps"], prom["latency_avg_ms"], prom["cache_hit_ratio"])
        return prom
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
        result = _run_trial(pg_params, trial.number)
        trial.set_user_attr("latency_avg_ms",  result["latency_avg_ms"])
        trial.set_user_attr("cache_hit_ratio", result["cache_hit_ratio"])
        return result["avg_tps"] if cfg.OBJECTIVE == "tps" else result["latency_avg_ms"]
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


# ── pgTune baseline ───────────────────────────────────────────────────────────

def _run_baseline(study: optuna.Study) -> None:
    """Run the pgTune baseline and inject the result directly into the study.

    Uses study.add_trial() instead of enqueue_trial() so SMAC's after_trial
    callback is never invoked for a seed-less trial, avoiding its intensifier
    assertion error.
    """
    raw = PGTUNE_BASELINES[cfg.WORKLOAD]
    pg_params = config_to_pg(raw)
    logger.info("Running pgTune baseline (trial 0)")
    try:
        result = _run_trial(pg_params, "pgTune")
        value = result["avg_tps"] if cfg.OBJECTIVE == "tps" else result["latency_avg_ms"]
        study.add_trial(optuna.trial.create_trial(
            params=raw,
            distributions=SEARCH_SPACE,
            value=value,
            user_attrs={
                "pg_config":       pg_params,
                "latency_avg_ms":  result["latency_avg_ms"],
                "cache_hit_ratio": result["cache_hit_ratio"],
            },
        ))
        logger.info("pgTune baseline: %.2f", value)
    except Exception as e:
        logger.warning("pgTune baseline failed: %s — proceeding without it", e)


# ── Warmup ────────────────────────────────────────────────────────────────────

def _warmup() -> None:
    logger.info("Warmup: running benchmark to prime buffer cache (results discarded)")
    run_benchmark(duration=cfg.BENCH_DURATION, workload=cfg.WORKLOAD)
    time.sleep(15)
    logger.info("Warmup complete")


# ── Runner ────────────────────────────────────────────────────────────────────

def run_optimization(trials: int, sampler: str = "smac") -> None:
    direction = "maximize" if cfg.OBJECTIVE == "tps" else "minimize"
    logger.info("Starting PostgreSQL Optimization (%s, %s, objective=%s) — %d trials",
                sampler.upper(), cfg.WORKLOAD.upper(), cfg.OBJECTIVE, trials)
    logger.info("Storage: %s | Study: %s", cfg.STORAGE_URL, cfg.STUDY_NAME)

    _warmup()

    study = optuna.create_study(
        storage=cfg.STORAGE_URL,
        study_name=cfg.STUDY_NAME,
        direction=direction,
        sampler=_build_sampler(sampler),
        load_if_exists=True,
    )

    if not study.trials:
        _run_baseline(study)

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
            best = study.best_trial
            logger.info("Best TPS:     %.2f", study.best_value)
            logger.info("Best latency: %.2f ms", best.user_attrs.get("latency_avg_ms", 0.0))
            logger.info("Best Config:  %s", best.params)
        except ValueError:
            logger.info("No trials completed successfully")
        logger.info("Visualize: optuna-dashboard %s", cfg.STORAGE_URL)
