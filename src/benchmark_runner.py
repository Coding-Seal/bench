import logging
import subprocess
import time

from .config import PG_DB, PG_USER

logger = logging.getLogger(__name__)

_PGBENCH_CMD = [
    "docker", "compose", "run", "--rm", "--no-deps", "pgbench",
    "pgbench", "-M", "prepared", "-U", PG_USER, "-d", PG_DB,
]


def run_benchmark(duration: int = 300, clients: int = 20, jobs: int = 20) -> tuple[int, int]:
    logger.info("Running pgbench: %ds | %d clients | %d threads", duration, clients, jobs)
    cmd = _PGBENCH_CMD + ["-c", str(clients), "-j", str(jobs), "-T", str(duration)]
    start_time = int(time.time())
    # start_new_session isolates docker from the terminal's process group so
    # Ctrl+C (SIGINT) reaches only Python, giving us clean control over shutdown.
    proc = subprocess.Popen(cmd, start_new_session=True)
    try:
        proc.wait()
    except KeyboardInterrupt:
        logger.warning("Interrupted — stopping pgbench container")
        subprocess.run(
            ["docker", "compose", "stop", "--timeout", "5", "pgbench"],
            check=False,
        )
        proc.wait()
        raise
    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd)
    return start_time, int(time.time())
