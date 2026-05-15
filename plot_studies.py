#!/usr/bin/env python3
"""Generate analysis plots from Optuna studies stored in optuna_study.db."""

import warnings
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import seaborn as sns
import optuna
from optuna.importance import get_param_importances
from pathlib import Path

warnings.filterwarnings("ignore")
optuna.logging.set_verbosity(optuna.logging.WARNING)

STORAGE = "sqlite:///optuna_study.db"
PLOTS_DIR = Path("thesis/sources")
PLOTS_DIR.mkdir(parents=True, exist_ok=True)

sns.set_theme(style="whitegrid", font_scale=1.15)
plt.rcParams.update({"figure.dpi": 150, "savefig.dpi": 150})

SMAC_COLOR = "#1565C0"
TPE_COLOR = "#C62828"

CONFIGS = {
    "oltp_tps": {
        "smac": [
            "pg_oltp_tps_smac_2026-05-13-23:45:44",
            "pg_oltp_tps_smac_2026-05-14-09:59:31",
            "pg_oltp_tps_smac_2026-05-14-20:13:34",
        ],
        "tpe": [
            "pg_oltp_tps_tpe_2026-05-14-01:27:04",
            "pg_oltp_tps_tpe_2026-05-14-11:40:56",
            "pg_oltp_tps_tpe_2026-05-14-21:55:21",
        ],
        "direction": "maximize",
        "ylabel": "TPS",
        "title": "OLTP — TPS",
    },
    "oltp_latency": {
        "smac": [
            "pg_oltp_latency_smac_2026-05-14-03:07:41",
            "pg_oltp_latency_smac_2026-05-14-13:21:33",
            "pg_oltp_latency_smac_2026-05-14-23:36:06",
        ],
        "tpe": [
            "pg_oltp_latency_tpe_2026-05-14-04:49:06",
            "pg_oltp_latency_tpe_2026-05-14-15:03:04",
            "pg_oltp_latency_tpe_2026-05-15-01:17:42",
        ],
        "direction": "minimize",
        "ylabel": "Latency (ms)",
        "title": "OLTP — Latency",
    },
    "olap_tps": {
        "smac": [
            "pg_olap_tps_smac_2026-05-14-06:29:32",
            "pg_olap_tps_smac_2026-05-14-16:43:39",
            "pg_olap_tps_smac_2026-05-15-02:58:32",
        ],
        "tpe": [
            "pg_olap_tps_tpe_2026-05-14-08:15:15",
            "pg_olap_tps_tpe_2026-05-14-18:28:39",
            "pg_olap_tps_tpe_2026-05-15-04:44:19",
        ],
        "direction": "maximize",
        "ylabel": "TPS",
        "title": "OLAP — TPS",
    },
}

PARAM_LABELS = {
    "shared_buffers_mb": "shared_buffers",
    "work_mem_kb": "work_mem",
    "maintenance_work_mem_mb": "maintenance_work_mem",
    "effective_cache_size_gb": "effective_cache_size",
    "huge_pages": "huge_pages",
    "wal_buffers_mb": "wal_buffers",
    "checkpoint_timeout_min": "checkpoint_timeout",
    "max_wal_size_gb": "max_wal_size",
    "min_wal_size_gb": "min_wal_size",
    "checkpoint_completion_target": "checkpoint_completion_target",
    "wal_compression": "wal_compression",
    "random_page_cost": "random_page_cost",
    "seq_page_cost": "seq_page_cost",
    "effective_io_concurrency": "effective_io_concurrency",
    "default_statistics_target": "default_statistics_target",
    "jit": "jit",
    "temp_buffers_mb": "temp_buffers",
    "bgwriter_lru_maxpages": "bgwriter_lru_maxpages",
    "bgwriter_delay_ms": "bgwriter_delay",
    "max_connections": "max_connections",
    "max_worker_processes": "max_worker_processes",
    "max_parallel_workers": "max_parallel_workers",
    "max_parallel_workers_per_gather": "max_parallel_workers_per_gather",
    "max_parallel_maintenance_workers": "max_parallel_maintenance_workers",
}


def load_study(name: str):
    return optuna.load_study(study_name=name, storage=STORAGE)


def trial_values(study) -> np.ndarray:
    return np.array(
        [
            t.value
            for t in study.trials
            if t.state == optuna.trial.TrialState.COMPLETE and t.value is not None
        ]
    )


def running_best(values: np.ndarray, direction: str) -> np.ndarray:
    if direction == "maximize":
        return np.maximum.accumulate(values)
    return np.minimum.accumulate(values)


def compute_best_curves(
    study_names: list[str], direction: str
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (x, mean_curve, std_curve) for a list of study names."""
    series = [running_best(trial_values(load_study(n)), direction) for n in study_names]
    max_len = max(len(s) for s in series)
    padded = np.array([np.pad(s, (0, max_len - len(s)), mode="edge") for s in series])
    x = np.arange(1, max_len + 1)
    return x, padded.mean(axis=0), padded.std(axis=0)


# ── 1. Convergence curves ─────────────────────────────────────────────────────


def plot_convergence():
    cfgs = list(CONFIGS.items())
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))

    for ax, (_, cfg) in zip(axes, cfgs):
        for label, color, key in [("SMAC", SMAC_COLOR, "smac"), ("TPE", TPE_COLOR, "tpe")]:
            x, mean, std = compute_best_curves(cfg[key], cfg["direction"])
            ax.plot(x, mean, color=color, label=label, linewidth=2)
            ax.fill_between(x, mean - std, mean + std, color=color, alpha=0.15)

        ax.set_title(cfg["title"], fontsize=13, fontweight="bold")
        ax.set_xlabel("Итерация")
        ax.set_ylabel(f"{cfg['ylabel']}")
        ax.legend(framealpha=0.9)
        ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True, nbins=8))

    fig.tight_layout()
    out = PLOTS_DIR / "convergence.svg"
    fig.savefig(out, format="svg", bbox_inches="tight")
    print(f"Saved {out}")
    plt.close(fig)


# ── 2. Parameter importance ───────────────────────────────────────────────────


def plot_param_importance():
    TOP_N = 12
    cfgs = list(CONFIGS.items())
    fig, axes = plt.subplots(1, 3, figsize=(17, 5))

    for ax, (_, cfg) in zip(axes, cfgs):
        all_importance: dict[str, list[float]] = {}
        for key in ("smac", "tpe"):
            for name in cfg[key]:
                study = load_study(name)
                try:
                    imp = get_param_importances(study)
                except Exception:
                    continue
                for param, val in imp.items():
                    all_importance.setdefault(param, []).append(val)

        mean_imp = {k: np.mean(v) for k, v in all_importance.items()}
        top_params = sorted(mean_imp, key=mean_imp.get, reverse=True)[:TOP_N]
        display_names = [PARAM_LABELS.get(p, p) for p in top_params]
        values = [mean_imp[p] for p in top_params]

        y = np.arange(len(top_params))
        bars = ax.barh(y, values, color="#00897B", edgecolor="white", linewidth=0.5)
        ax.set_yticks(y)
        ax.set_yticklabels(display_names, fontsize=9.5)
        ax.invert_yaxis()
        ax.set_title(cfg["title"], fontsize=13, fontweight="bold")
        ax.set_xlabel("Важность параметра")
        ax.xaxis.set_major_locator(ticker.MaxNLocator(nbins=5))

        for bar, val in zip(bars, values):
            ax.text(
                val + max(values) * 0.01,
                bar.get_y() + bar.get_height() / 2,
                f"{val:.3f}",
                va="center",
                fontsize=8.5,
            )

    fig.tight_layout()
    out = PLOTS_DIR / "param_importance.svg"
    fig.savefig(out, format="svg", bbox_inches="tight")
    print(f"Saved {out}")
    plt.close(fig)


BASELINE_COLOR = "#78909C"


def _collect_gains(cfg: dict) -> dict:
    """Return means and stds for baseline, SMAC, TPE for one workload config."""
    direction = cfg["direction"]
    baselines, smac_bests, tpe_bests = [], [], []
    for sampler_key, dest in [("smac", smac_bests), ("tpe", tpe_bests)]:
        for name in cfg[sampler_key]:
            study = load_study(name)
            trials = [
                t
                for t in study.trials
                if t.state == optuna.trial.TrialState.COMPLETE and t.value is not None
            ]
            baselines.append(trials[0].value)
            best = (
                max(t.value for t in trials)
                if direction == "maximize"
                else min(t.value for t in trials)
            )
            dest.append(best)
    return {
        "baseline_mean": np.mean(baselines),
        "baseline_std": np.std(baselines),
        "smac_mean": np.mean(smac_bests),
        "smac_std": np.std(smac_bests),
        "tpe_mean": np.mean(tpe_bests),
        "tpe_std": np.std(tpe_bests),
    }


def _pct_gain(optimized: float, baseline: float, direction: str) -> float:
    if direction == "maximize":
        return (optimized - baseline) / baseline * 100
    return (baseline - optimized) / baseline * 100


# ── 3. Gains bar chart ────────────────────────────────────────────────────────


def plot_gains():
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    bar_width = 0.25
    x = np.array([0.0])

    for ax, (_, cfg) in zip(axes, CONFIGS.items()):
        g = _collect_gains(cfg)
        direction = cfg["direction"]

        means = [g["baseline_mean"], g["smac_mean"], g["tpe_mean"]]
        stds = [g["baseline_std"], g["smac_std"], g["tpe_std"]]
        colors = [BASELINE_COLOR, SMAC_COLOR, TPE_COLOR]
        labels = ["pgTune", "SMAC", "TPE"]

        # Pre-compute y range so annotation positions are stable
        all_vals = [m - s for m, s in zip(means, stds)] + [m + s for m, s in zip(means, stds)]
        margin = (max(all_vals) - min(all_vals)) * 0.4
        ymin = max(0, min(all_vals) - margin)
        ymax = max(all_vals) + margin
        ax.set_ylim(ymin, ymax)

        offsets = np.array([-bar_width, 0.0, bar_width])
        for offset, mean, std, color, label in zip(offsets, means, stds, colors, labels):
            ax.bar(
                x + offset,
                mean,
                bar_width * 0.9,
                color=color,
                label=label,
                yerr=std,
                capsize=5,
                error_kw={"elinewidth": 1.5, "ecolor": "black"},
            )
            if label != "pgTune":
                gain = _pct_gain(mean, g["baseline_mean"], direction)
                sign = "+" if gain >= 0 else ""
                ax.text(
                    x[0] + offset,
                    mean + std + (ymax - ymin) * 0.015,
                    f"{sign}{gain:.1f}%",
                    ha="center",
                    va="bottom",
                    fontsize=10,
                    fontweight="bold",
                    color=color,
                )

        ax.set_title(cfg["title"], fontsize=13, fontweight="bold")
        ax.set_ylabel(f"Лучший {cfg['ylabel']}")
        ax.set_xticks([])
        ax.legend(fontsize=9.5, framealpha=0.9)

    fig.tight_layout()
    out = PLOTS_DIR / "gains_barchart.svg"
    fig.savefig(out, format="svg", bbox_inches="tight")
    print(f"Saved {out}")
    plt.close(fig)


if __name__ == "__main__":
    print("Generating plots…")
    plot_convergence()
    plot_param_importance()
    plot_gains()
    print(f"Done! Plots saved to {PLOTS_DIR}/")
