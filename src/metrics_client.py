import logging
import math
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
                logger.warning(
                    "Prometheus unreachable — retrying in %.0fs (%d/%d): %s",
                    delay,
                    attempt + 1,
                    retries,
                    e,
                )
                time.sleep(delay)
            else:
                raise
        except requests.HTTPError as e:
            is_server_error = e.response is not None and e.response.status_code >= 500
            if is_server_error and attempt < retries - 1:
                logger.warning(
                    "Prometheus %s — retrying in %.0fs (%d/%d)", e, delay, attempt + 1, retries
                )
                time.sleep(delay)
            else:
                raise


def _range_avg(data: dict) -> float:
    """Average a query_range result, dropping non-finite values. Raises on empty result."""
    if data["status"] != "success" or not data["data"]["result"]:
        raise RuntimeError("Prometheus returned no data for query")
    values = [
        float(v[1]) for v in data["data"]["result"][0]["values"] if math.isfinite(float(v[1]))
    ]
    if not values:
        raise RuntimeError("Prometheus result contained only non-finite values")
    return sum(values) / len(values)


def poll_prometheus_metrics(start_ts: int, end_ts: int) -> dict:
    params = {"start": start_ts, "end": end_ts, "step": "15s"}

    tps_data = _get(
        f"{PROMETHEUS_URL}/api/v1/query_range",
        {
            **params,
            "query": f'rate(pg_stat_database_xact_commit{{datname="{PG_DB}"}}[1m])',
        },
    )
    avg_tps = _range_avg(tps_data)

    # active CPU time / committed transactions * 1000 → ms
    latency_data = _get(
        f"{PROMETHEUS_URL}/api/v1/query_range",
        {
            **params,
            "query": (
                f'rate(pg_stat_database_active_time_seconds_total{{datname="{PG_DB}"}}[1m])'
                f' / rate(pg_stat_database_xact_commit{{datname="{PG_DB}"}}[1m])'
                f" * 1000"
            ),
        },
    )
    avg_latency_ms = _range_avg(latency_data)

    # Per-trial cache hit ratio via rate() — avoids cumulative counter dominating the result
    hit_data = _get(
        f"{PROMETHEUS_URL}/api/v1/query_range",
        {
            **params,
            "query": (
                f'rate(pg_stat_database_blks_hit{{datname="{PG_DB}"}}[1m])'
                f" / ("
                f'rate(pg_stat_database_blks_hit{{datname="{PG_DB}"}}[1m])'
                f' + rate(pg_stat_database_blks_read{{datname="{PG_DB}"}}[1m])'
                f") * 100"
            ),
        },
    )
    try:
        cache_hit = _range_avg(hit_data)
    except RuntimeError:
        cache_hit = 0.0

    return {
        "avg_tps": avg_tps,
        "latency_avg_ms": avg_latency_ms,
        "cache_hit_ratio": cache_hit,
    }
