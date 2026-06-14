import queue
import threading

from module.dashboard_sync.client import push_dashboard_snapshot, resolve_dashboard_api_settings
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
                push_dashboard_snapshot(**item)
            except Exception as exc:
                logger.warning(f"Dashboard API push skipped: {exc}")

    def queue_snapshot(self, config, recorded_at_ms: int, resources: dict):
        settings = resolve_dashboard_api_settings(config)
        if settings is None:
            return
        self._ensure_thread()
        payload = {
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


_dispatcher = DashboardSyncDispatcher()


def queue_dashboard_snapshot(config, recorded_at_ms: int, resources: dict):
    _dispatcher.queue_snapshot(config, recorded_at_ms, resources)
