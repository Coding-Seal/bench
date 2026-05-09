import argparse
import logging

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
    parser.add_argument("--direction", choices=["maximize", "minimize"], default="maximize")
    parser.add_argument("--duration",  type=int, default=None,
                        help="pgbench seconds per trial (overrides BENCH_DURATION env var)")
    args = parser.parse_args()

    _setup_logging()

    if args.duration is not None:
        cfg.BENCH_DURATION = args.duration

    run_optimization(trials=args.trials, direction=args.direction, sampler=args.sampler)


if __name__ == "__main__":
    main()
