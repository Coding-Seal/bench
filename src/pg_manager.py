import logging
import re
import shutil
import subprocess
import time

from .config import BACKUP_PATH, CONFIG_PATH, PG_DB, PG_SERVICE, PG_USER, RESTART_REQUIRED_PARAMS

logger = logging.getLogger(__name__)


def run_docker_cmd(cmd: list, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def backup_config() -> None:
    if CONFIG_PATH.exists():
        shutil.copy2(CONFIG_PATH, BACKUP_PATH)


def restore_config() -> None:
    if BACKUP_PATH.exists():
        shutil.copy2(BACKUP_PATH, CONFIG_PATH)


def apply_config(params: dict) -> bool:
    lines = CONFIG_PATH.read_text().splitlines()

    # Parse current values to detect whether restart-required params actually changed.
    current = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        m = re.match(r'([a-z_][a-z0-9_]*)\s*=\s*(.+)', stripped, re.IGNORECASE)
        if m:
            current[m.group(1).lower()] = m.group(2).strip()

    new_lines = []
    applied_keys = set()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            new_lines.append(line)
            continue
        m = re.match(r'([a-z_][a-z0-9_]*)\s*=', stripped, re.IGNORECASE)
        if m:
            key = m.group(1).lower()
            if key in params:
                indent = line[:len(line) - len(line.lstrip())]
                new_lines.append(f"{indent}{key} = {params[key]}")
                applied_keys.add(key)
                continue
        new_lines.append(line)

    for k, v in params.items():
        if k not in applied_keys:
            new_lines.append(f"{k} = {v}")

    CONFIG_PATH.write_text("\n".join(new_lines) + "\n")

    return any(
        k in RESTART_REQUIRED_PARAMS and str(params[k]) != current.get(k)
        for k in params
    )


def wait_for_postgres(timeout: int = 60) -> None:
    cmd = ["docker", "compose", "exec", "-T", PG_SERVICE, "pg_isready", "-U", PG_USER]
    start = time.time()
    while time.time() - start < timeout:
        if subprocess.run(cmd, capture_output=True).returncode == 0:
            return
        time.sleep(2)
    raise RuntimeError(f"PostgreSQL did not become ready within {timeout}s")


def reload_or_restart(needs_restart: bool) -> None:
    if needs_restart:
        logger.info("Restarting PostgreSQL (restart-required params changed)")
        run_docker_cmd(["docker", "compose", "restart", PG_SERVICE])
    else:
        logger.info("Reloading PostgreSQL configuration")
        run_docker_cmd([
            "docker", "compose", "exec", "-T", PG_SERVICE,
            "psql", "-U", PG_USER, "-d", PG_DB,
            "-c", "SELECT pg_reload_conf();"
        ])
    wait_for_postgres()
