import os
from dataclasses import dataclass, field
from typing import List

import yaml


@dataclass
class ApiConfig:
    host: str = "0.0.0.0"
    port: int = 22367
    log_level: str = "info"
    database_url: str = "sqlite:///./data/dashboard_api.db"
    admin_token: str = "change-me-admin-token"
    cors_allowed_origins: List[str] = field(default_factory=list)


def _read_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Invalid dashboard api config: {path}")
    return data


def load_api_config(path: str) -> ApiConfig:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Dashboard API config not found: {path}. Copy config/dashboard_api.template.yaml first."
        )

    raw = _read_yaml(path)
    server = raw.get("server", {})
    database = raw.get("database", {})
    auth = raw.get("auth", {})

    return ApiConfig(
        host=str(server.get("host", "0.0.0.0")),
        port=int(server.get("port", 22367)),
        log_level=str(server.get("log_level", "info")),
        database_url=str(database.get("url", "sqlite:///./data/dashboard_api.db")),
        admin_token=str(auth.get("admin_token", "change-me-admin-token")),
        cors_allowed_origins=list(raw.get("cors_allowed_origins", [])),
    )
