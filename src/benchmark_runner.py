import subprocess
import time
from .config import PG_USER, PG_DB

def run_benchmark(duration: int = 300, clients: int = 20, jobs: int = 20) -> tuple[int, int]:
    print(f"🚀 Running pgbench: {duration}s | {clients} clients | {jobs} threads")
    start_time = int(time.time())
    subprocess.run([
        "docker", "compose", "run", "--rm", "--no-deps", "pgbench",
        "pgbench", "-c", str(clients), "-j", str(jobs), "-T", str(duration),
        "-M", "prepared", "-U", PG_USER, "-d", PG_DB
    ], check=True)
    end_time = int(time.time())
    return start_time, end_time