import hashlib
import re
import secrets
import time

RESOURCE_NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")
DEFAULT_RESOURCE_ORDER = [
    "Oil",
    "Coin",
    "Gem",
    "Cube",
    "Pt",
    "ActionPoint",
    "YellowCoin",
    "PurpleCoin",
    "Core",
    "Medal",
    "Merit",
    "GuildCoin",
]


def now_ms() -> int:
    return int(time.time() * 1000)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def is_valid_resource_name(name: str) -> bool:
    return bool(RESOURCE_NAME_RE.fullmatch(name or ""))


def sort_resource_names(names):
    ordered = [name for name in DEFAULT_RESOURCE_ORDER if name in names]
    extras = sorted([name for name in names if name not in DEFAULT_RESOURCE_ORDER])
    return ordered + extras
