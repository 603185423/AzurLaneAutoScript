import json
from urllib import error, request

from module.config.deep import deep_get
from module.dashboard_sync.payload import build_push_payload
from module.logger import logger


def resolve_dashboard_api_settings(config):
    base = deep_get(config.data, "DashboardSettings.DashboardAPI.BaseURL", default="")
    token = deep_get(config.data, "DashboardSettings.DashboardAPI.Token", default="")
    enabled = deep_get(config.data, "DashboardSettings.DashboardAPI.Enable", default=False)
    timeout = deep_get(config.data, "DashboardSettings.DashboardAPI.Timeout", default=3)

    if not enabled:
        return None
    base = str(base).strip()
    token = str(token).strip()
    if not base or not token:
        return None
    try:
        timeout = float(timeout)
    except (TypeError, ValueError):
        timeout = 3
    return {
        "base_url": base.rstrip("/"),
        "token": token,
        "timeout": max(timeout, 0.5),
        "config_name": getattr(config, "config_name", "alas"),
    }


def build_api_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def push_dashboard_snapshot(*, base_url: str, token: str, timeout: float, config_name: str, recorded_at_ms: int, resources: dict):
    payload = build_push_payload(config_name=config_name, recorded_at_ms=recorded_at_ms, resources=resources)
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        f"{base_url}/api/v1/pushes",
        data=body,
        headers=build_api_headers(token),
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as response:
            if response.status >= 400:
                text = response.read().decode("utf-8", errors="replace").strip().replace("\n", " ")
                raise RuntimeError(f"dashboard api push failed: {response.status} {text[:200]}")
    except error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace").strip().replace("\n", " ")
        raise RuntimeError(f"dashboard api push failed: {exc.code} {text[:200]}")
    logger.info(f"Dashboard API push accepted: {list(resources.keys())}")
