from datetime import datetime

from cached_property import cached_property

from module.config.deep import deep_get
from module.logger import logger


class LogRes:
    """
    Update dashboard resources through config.modified.

    Usage:
        LogRes(config).Cube = 10
        LogRes(config).Oil = {"Value": 1200, "Limit": 25000}
    """

    def __init__(self, config):
        self.__dict__["config"] = config

    def __setattr__(self, key, value):
        if key not in self.groups:
            logger.info("No such resource on dashboard")
            super().__setattr__(name=key, value=value)
            return

        key_group = f"Dashboard.{key}"
        original = deep_get(self.config.data, keys=key_group)
        record_time = datetime.now().replace(microsecond=0)

        if isinstance(value, int):
            if original["Value"] != value:
                self.config.modified[f"{key_group}.Value"] = value
                self.config.modified[f"{key_group}.Record"] = record_time
            return

        if isinstance(value, dict):
            modified = False
            for value_name, current_value in value.items():
                if current_value == original[value_name]:
                    continue
                self.config.modified[f"{key_group}.{value_name}"] = current_value
                modified = True
            if modified:
                self.config.modified[f"{key_group}.Record"] = record_time
            return

        logger.info("Unsupported dashboard resource value type")

    @cached_property
    def groups(self) -> dict:
        from module.config.utils import filepath_argument, read_file

        return deep_get(read_file(filepath_argument("dashboard")), keys="Dashboard")
