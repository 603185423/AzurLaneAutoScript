import json
from urllib import error, request

from module.config.deep import deep_get
from module.config.utils import filepath_config, read_file
from module.dashboard_sync.payload import build_event_payload, build_push_payload
from module.logger import logger


def _normalize_dashboard_api_settings(*, data: dict, config_name: str):
    base = deep_get(data, "DashboardSettings.DashboardAPI.BaseURL", default="")
    token = deep_get(data, "DashboardSettings.DashboardAPI.Token", default="")
    enabled = deep_get(data, "DashboardSettings.DashboardAPI.Enable", default=False)
    timeout = deep_get(data, "DashboardSettings.DashboardAPI.Timeout", default=3)

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
        "config_name": config_name,
    }


def resolve_dashboard_api_settings(config):
    return _normalize_dashboard_api_settings(
        data=config.data,
        config_name=getattr(config, "config_name", "alas"),
    )


def resolve_dashboard_api_settings_by_name(config_name: str):
    data = read_file(filepath_config(config_name))
    if not isinstance(data, dict):
        return None
    return _normalize_dashboard_api_settings(data=data, config_name=config_name)


def build_api_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _post_json(*, base_url: str, path: str, token: str, timeout: float, payload: dict):
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        f"{base_url}{path}",
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


def push_dashboard_snapshot(*, base_url: str, token: str, timeout: float, config_name: str, recorded_at_ms: int, resources: dict):
    payload = build_push_payload(config_name=config_name, recorded_at_ms=recorded_at_ms, resources=resources)
    _post_json(
        base_url=base_url,
        path="/api/v1/pushes",
        token=token,
        timeout=timeout,
        payload=payload,
    )
    logger.info(f"Dashboard API push accepted: {list(resources.keys())}")


def push_script_event(
    *,
    base_url: str,
    token: str,
    timeout: float,
    config_name: str,
    event_category: str,
    event_type: str,
    status: str = None,
    reason: str = None,
    recorded_at_ms: int,
    payload: dict = None,
):
    event_payload = build_event_payload(
        config_name=config_name,
        event_category=event_category,
        event_type=event_type,
        status=status,
        reason=reason,
        recorded_at_ms=recorded_at_ms,
        payload=payload,
    )
    _post_json(
        base_url=base_url,
        path="/api/v1/events",
        token=token,
        timeout=timeout,
        payload=event_payload,
    )
    logger.info(f"Dashboard API event accepted: {event_category}/{event_type}")


def push_script_event_by_config_name(
    config_name: str,
    *,
    event_category: str,
    event_type: str,
    status: str = None,
    reason: str = None,
    recorded_at_ms: int,
    payload: dict = None,
):
    settings = resolve_dashboard_api_settings_by_name(config_name)
    if settings is None:
        return
    push_script_event(
        base_url=settings["base_url"],
        token=settings["token"],
        timeout=settings["timeout"],
        config_name=settings["config_name"],
        event_category=event_category,
        event_type=event_type,
        status=status,
        reason=reason,
        recorded_at_ms=recorded_at_ms,
        payload=payload,
    )
