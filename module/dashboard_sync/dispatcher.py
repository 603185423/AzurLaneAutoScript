import queue
import threading

from module.dashboard_sync.client import (
    push_dashboard_snapshot,
    push_script_event,
    resolve_dashboard_api_settings,
    resolve_dashboard_api_settings_by_name,
)
from module.logger import logger


class DashboardSyncDispatcher:
    def __init__(self):
        self._queue = queue.Queue(maxsize=256)
        self._thread = None
        self._lock = threading.Lock()

    def _ensure_thread(self):
        if self._thread and self._thread.is_alive():
            return
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._thread = threading.Thread(target=self._worker, name="dashboard-sync", daemon=True)
            self._thread.start()

    def _worker(self):
        while True:
            item = self._queue.get()
            try:
                kind = item.pop("kind")
                if kind == "resource":
                    push_dashboard_snapshot(**item)
                elif kind == "event":
                    push_script_event(**item)
                else:
                    logger.warning(f"Unknown dashboard sync payload kind: {kind}")
            except Exception as exc:
                logger.warning(f"Dashboard API push skipped: {exc}")

    def queue_snapshot(self, config, recorded_at_ms: int, resources: dict):
        settings = resolve_dashboard_api_settings(config)
        if settings is None:
            return
        self._ensure_thread()
        payload = {
            "kind": "resource",
            "base_url": settings["base_url"],
            "token": settings["token"],
            "timeout": settings["timeout"],
            "config_name": settings["config_name"],
            "recorded_at_ms": recorded_at_ms,
            "resources": resources,
        }
        try:
            self._queue.put_nowait(payload)
        except queue.Full:
            logger.warning("Dashboard API push queue is full, drop newest snapshot")

    def queue_event(
        self,
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
        self._ensure_thread()
        item = {
            "kind": "event",
            "base_url": settings["base_url"],
            "token": settings["token"],
            "timeout": settings["timeout"],
            "config_name": settings["config_name"],
            "event_category": event_category,
            "event_type": event_type,
            "status": status,
            "reason": reason,
            "recorded_at_ms": recorded_at_ms,
            "payload": payload,
        }
        try:
            self._queue.put_nowait(item)
        except queue.Full:
            logger.warning("Dashboard API push queue is full, drop newest event")


_dispatcher = DashboardSyncDispatcher()


def queue_dashboard_snapshot(config, recorded_at_ms: int, resources: dict):
    _dispatcher.queue_snapshot(config, recorded_at_ms, resources)


def queue_script_event(
    config_name: str,
    *,
    event_category: str,
    event_type: str,
    status: str = None,
    reason: str = None,
    recorded_at_ms: int,
    payload: dict = None,
):
    _dispatcher.queue_event(
        config_name,
        event_category=event_category,
        event_type=event_type,
        status=status,
        reason=reason,
        recorded_at_ms=recorded_at_ms,
        payload=payload,
    )
