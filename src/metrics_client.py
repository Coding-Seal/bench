import requests
from .config import PROMETHEUS_URL, PG_DB

def poll_prometheus_metrics(start_ts: int, end_ts: int) -> dict:
    # Average TPS over benchmark window
    tps_query = f'rate(pg_stat_database_xact_commit{{datname="{PG_DB}"}}[1m])'
    resp = requests.get(f"{PROMETHEUS_URL}/api/v1/query_range", params={
        "query": tps_query, "start": start_ts, "end": end_ts, "step": "15s"
    })
    resp.raise_for_status()
    data = resp.json()

    tps_values = []
    if data["status"] == "success" and data["data"]["result"]:
        tps_values = [float(v[1]) for v in data["data"]["result"][0]["values"]]

    avg_tps = sum(tps_values) / len(tps_values) if tps_values else 0.0

    # Cache hit ratio at end of run
    hit_query = (
        f'sum(pg_stat_database_blks_hit{{datname="{PG_DB}"}}) / '
        f'(sum(pg_stat_database_blks_hit{{datname="{PG_DB}"}}) + sum(pg_stat_database_blks_read{{datname="{PG_DB}"}})) * 100'
    )
    hit_resp = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": hit_query, "time": end_ts})
    hit_resp.raise_for_status()
    hit_data = hit_resp.json()
    
    cache_hit = 0.0
    if hit_data["status"] == "success" and hit_data["data"]["result"]:
        cache_hit = float(hit_data["data"]["result"][0]["value"][1])

    return {"avg_tps": avg_tps, "cache_hit_ratio": cache_hit}