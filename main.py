import argparse
from src.optimizer import run_optimization

def main():
    parser = argparse.ArgumentParser(description="PostgreSQL Configuration Optimizer")
    parser.add_argument("--trials", type=int, default=20, help="Number of Optuna trials")
    parser.add_argument("--direction", choices=["maximize", "minimize"], default="maximize")
    parser.add_argument("--duration", type=int, default=60, help="pgbench duration per trial (seconds)")
    args = parser.parse_args()

    run_optimization(
        trials=args.trials,
        direction=args.direction,
    )

if __name__ == "__main__":
    main()