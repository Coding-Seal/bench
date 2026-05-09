import argparse
import logging
from datetime import datetime

import src.config as cfg
from src.optimizer import run_optimization


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )
    # Silence third-party loggers — their output adds noise without value
    logging.getLogger("smac").setLevel(logging.WARNING)
    logging.getLogger("optuna").setLevel(logging.WARNING)


def main() -> None:
    parser = argparse.ArgumentParser(description="PostgreSQL Configuration Optimizer")
    parser.add_argument("--trials",    type=int, default=20)
    parser.add_argument("--sampler",   choices=["smac", "tpe"], default="smac")
    parser.add_argument("--objective", choices=["tps", "latency"], default=None,
                        help="metric to optimize (overrides OBJECTIVE env var)")
    parser.add_argument("--duration",  type=int, default=None,
                        help="pgbench seconds per trial (overrides BENCH_DURATION env var)")
    parser.add_argument("--workload",  choices=["oltp", "olap"], default=None,
                        help="benchmark workload (overrides WORKLOAD env var)")
    parser.add_argument("--continue",  dest="study_name", metavar="STUDY_NAME",
                        help="resume an existing study by name instead of creating a new one")
    args = parser.parse_args()

    _setup_logging()

    if args.objective is not None:
        cfg.OBJECTIVE = args.objective
    if args.duration is not None:
        cfg.BENCH_DURATION = args.duration
    if args.workload is not None:
        cfg.WORKLOAD = args.workload

    cfg.STUDY_NAME = args.study_name or (
        f"pg_{cfg.WORKLOAD}_{cfg.OBJECTIVE}_{args.sampler}"
        f"_{datetime.now().strftime('%Y-%m-%d-%H:%M:%S')}"
    )

    run_optimization(trials=args.trials, sampler=args.sampler)


if __name__ == "__main__":
    main()
