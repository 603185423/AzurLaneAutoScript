import argparse

import uvicorn

from module.dashboard_api.app import create_app
from module.dashboard_api.config import load_api_config
from module.logger import logger


def main():
    parser = argparse.ArgumentParser(description="Alas dashboard api service")
    parser.add_argument(
        "--config",
        type=str,
        default="./config/dashboard_api.yaml",
        help="Dashboard API config yaml path",
    )
    parser.add_argument("--host", type=str, help="Override host from config")
    parser.add_argument("--port", type=int, help="Override port from config")
    args = parser.parse_args()

    api_config = load_api_config(args.config)
    host = args.host or api_config.host
    port = args.port or api_config.port

    logger.hr("Dashboard API config", level=0)
    logger.attr("Config", args.config)
    logger.attr("Host", host)
    logger.attr("Port", port)
    logger.attr("Database", api_config.database_url)

    uvicorn.run(
        create_app(args.config),
        host=host,
        port=port,
        log_level=api_config.log_level,
    )


if __name__ == "__main__":
    main()
