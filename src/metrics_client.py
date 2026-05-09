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


def _range_avg(data: dict) -> float:
    """Average a query_range result, dropping NaN and Inf."""
    if data["status"] != "success" or not data["data"]["result"]:
        return 0.0
    values = []
    for v in data["data"]["result"][0]["values"]:
        f = float(v[1])
        if f == f and f != float("inf"):  # drop NaN / Inf
            values.append(f)
    return sum(values) / len(values) if values else 0.0


def poll_prometheus_metrics(start_ts: int, end_ts: int) -> dict:
    params = {"start": start_ts, "end": end_ts, "step": "15s"}

    # Average TPS over the benchmark window
    tps_data = _get(f"{PROMETHEUS_URL}/api/v1/query_range", {
        **params,
        "query": f'rate(pg_stat_database_xact_commit{{datname="{PG_DB}"}}[1m])',
    })
    avg_tps = _range_avg(tps_data)

    # Average transaction latency (ms) = active CPU time / committed transactions
    latency_data = _get(f"{PROMETHEUS_URL}/api/v1/query_range", {
        **params,
        "query": (
            f'rate(pg_stat_database_active_time_seconds_total{{datname="{PG_DB}"}}[1m])'
            f' / rate(pg_stat_database_xact_commit{{datname="{PG_DB}"}}[1m])'
            f' * 1000'
        ),
    })
    avg_latency_ms = _range_avg(latency_data)

    # Cache hit ratio at end of window
    hit_data = _get(f"{PROMETHEUS_URL}/api/v1/query", {
        "time": end_ts,
        "query": (
            f'sum(pg_stat_database_blks_hit{{datname="{PG_DB}"}}) /'
            f'(sum(pg_stat_database_blks_hit{{datname="{PG_DB}"}}) +'
            f' sum(pg_stat_database_blks_read{{datname="{PG_DB}"}})) * 100'
        ),
    })
    cache_hit = 0.0
    if hit_data["status"] == "success" and hit_data["data"]["result"]:
        cache_hit = float(hit_data["data"]["result"][0]["value"][1])

    return {
        "avg_tps":        avg_tps,
        "latency_avg_ms": avg_latency_ms,
        "cache_hit_ratio": cache_hit,
    }
