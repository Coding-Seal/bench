import subprocess
import time
import re
import shutil
from .config import CONFIG_PATH, BACKUP_PATH, PG_USER, PG_DB, PG_SERVICE, RESTART_REQUIRED_PARAMS

def run_docker_cmd(cmd: list, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=check)

def backup_config():
    if CONFIG_PATH.exists():
        # Use shutil.copy2 instead of rename to avoid cross-ownership permission errors
        shutil.copy2(CONFIG_PATH, BACKUP_PATH)

def restore_config():
    if BACKUP_PATH.exists():
        shutil.copy2(BACKUP_PATH, CONFIG_PATH)

def apply_config(params: dict) -> bool:
    lines = CONFIG_PATH.read_text().splitlines()
    new_lines = []
    applied_keys = set()

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            new_lines.append(line)
            continue

        match = re.match(r'([a-z_][a-z0-9_]*)\s*=', stripped, re.IGNORECASE)
        if match:
            key = match.group(1).lower()
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
    return bool(set(params.keys()) & RESTART_REQUIRED_PARAMS)

def wait_for_postgres(timeout: int = 60):
    cmd = ["docker", "compose", "exec", "-T", PG_SERVICE, "pg_isready", "-U", PG_USER]
    start = time.time()
    while time.time() - start < timeout:
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode == 0:
            return True
        time.sleep(2)
    raise RuntimeError(f"PostgreSQL did not become ready within {timeout}s")

def reload_or_restart(needs_restart: bool):
    if needs_restart:
        print("🔄 Restarting PostgreSQL (restart-required params changed)...")
        run_docker_cmd(["docker", "compose", "restart", PG_SERVICE])
    else:
        print("🔄 Reloading PostgreSQL configuration...")
        run_docker_cmd([
            "docker", "compose", "exec", "-T", PG_SERVICE,
            "psql", "-U", PG_USER, "-d", PG_DB,
            "-c", "SELECT pg_reload_conf();"
        ])
    wait_for_postgres()