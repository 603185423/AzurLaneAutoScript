from datetime import datetime


def datetime_to_unix_ms(value: datetime) -> int:
    return int(value.timestamp() * 1000)


def normalize_color(value):
    if value is None:
        return None
    return str(value).replace("^", "#")


def build_resource_payload(group: dict) -> dict:
    payload = {
        "value": int(group.get("Value", 0)),
    }
    if "Limit" in group:
        payload["limit"] = int(group.get("Limit", 0))
    if "Total" in group:
        payload["total"] = int(group.get("Total", 0))
    color = normalize_color(group.get("Color"))
    if color:
        payload["color"] = color
    return payload


def build_push_payload(config_name: str, recorded_at_ms: int, resources: dict) -> dict:
    return {
        "source": {
            "instance": config_name,
            "config": config_name,
            "producer": "AzurLaneAutoScript",
        },
        "recorded_at_ms": recorded_at_ms,
        "resources": resources,
    }
