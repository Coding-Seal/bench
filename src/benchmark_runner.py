import logging
import subprocess
import time

from .config import PG_DB, PG_USER

logger = logging.getLogger(__name__)

_WORKLOAD_DEFAULTS = {
    "oltp": {"clients": 20, "jobs": 20, "mode": "prepared", "script": None},
    "olap": {"clients": 4,  "jobs": 4,  "mode": "simple",   "script": "/pgbench_scripts/olap.sql"},
}


def run_benchmark(duration: int = 300, workload: str = "oltp") -> tuple[int, int]:
    defaults = _WORKLOAD_DEFAULTS[workload]
    clients, jobs, mode, script = (
        defaults["clients"], defaults["jobs"], defaults["mode"], defaults["script"],
    )
    logger.info("pgbench [%s]: %ds | %d clients | %d threads", workload, duration, clients, jobs)

    cmd = [
        "docker", "compose", "run", "--rm", "--no-deps", "pgbench",
        "pgbench",
        "-c", str(clients), "-j", str(jobs), "-T", str(duration),
        "-M", mode, "-U", PG_USER, "-d", PG_DB,
    ]
    if script:
        cmd += ["-f", script]

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
