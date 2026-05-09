import logging
import time

import requests

from .config import PG_DB, PROMETHEUS_URL

logger = logging.getLogger(__name__)

_session = requests.Session()


def _get(url: str, params: dict, retries: int = 5, delay: float = 30.0) -> dict:
    for attempt in range(retries):
        try:
            resp = _session.get(url, params=params, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except (requests.ConnectionError, requests.Timeout) as e:
            if attempt < retries - 1:
                logger.warning("Prometheus unreachable — retrying in %.0fs (%d/%d): %s",
                               delay, attempt + 1, retries, e)
                time.sleep(delay)
                continue
            raise
        except requests.HTTPError as e:
            is_server_error = e.response is not None and e.response.status_code >= 500
            if is_server_error and attempt < retries - 1:
                logger.warning("Prometheus %s — retrying in %.0fs (%d/%d)",
                               e, delay, attempt + 1, retries)
                time.sleep(delay)
                continue
            raise


def poll_prometheus_metrics(start_ts: int, end_ts: int) -> dict:
    tps_query = f'rate(pg_stat_database_xact_commit{{datname="{PG_DB}"}}[1m])'
    data = _get(f"{PROMETHEUS_URL}/api/v1/query_range", {
        "query": tps_query, "start": start_ts, "end": end_ts, "step": "15s",
    })
    tps_values = []
    if data["status"] == "success" and data["data"]["result"]:
        tps_values = [float(v[1]) for v in data["data"]["result"][0]["values"]]
    avg_tps = sum(tps_values) / len(tps_values) if tps_values else 0.0

    hit_query = (
        f'sum(pg_stat_database_blks_hit{{datname="{PG_DB}"}}) / '
        f'(sum(pg_stat_database_blks_hit{{datname="{PG_DB}"}}) + '
        f'sum(pg_stat_database_blks_read{{datname="{PG_DB}"}})) * 100'
    )
    hit_data = _get(f"{PROMETHEUS_URL}/api/v1/query", {"query": hit_query, "time": end_ts})
    cache_hit = 0.0
    if hit_data["status"] == "success" and hit_data["data"]["result"]:
        cache_hit = float(hit_data["data"]["result"][0]["value"][1])

    return {"avg_tps": avg_tps, "cache_hit_ratio": cache_hit}
