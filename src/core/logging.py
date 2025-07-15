# src/core/logging.py
import logging
import logging.config
import sys
from pathlib import Path
from typing import Any

import structlog
from structlog.types import Processor

from src.core.config import settings


# --- Custom Processors ---
def add_app_context(logger: Any, method_name: str, event_dict: dict) -> dict:
    """Add application context to all log entries."""
    event_dict["app"] = "fund-report-scraper"
    event_dict["version"] = settings.project_version
    return event_dict


def configure_logging(log_level: str = settings.logging.level):
    """
    Configure structured logging for the entire application.
    - Logs are sent to a rotating file in JSON format.
    - Logs are also sent to the console with human-readable, colored output.
    """
    log_level = log_level.upper()
    log_dir = Path(settings.logging.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    # Define shared processors for all logs
    shared_processors: list[Processor] = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        add_app_context,
    ]

    # Configure the standard library logging foundation
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,  # Keep third-party loggers
            "formatters": {
                "json": {
                    "()": structlog.stdlib.ProcessorFormatter,
                    "processor": structlog.processors.JSONRenderer(),
                    "foreign_pre_chain": shared_processors,
                },
                "console": {
                    "()": structlog.stdlib.ProcessorFormatter,
                    "processor": structlog.dev.ConsoleRenderer(colors=True),
                    "foreign_pre_chain": shared_processors,
                },
            },
            "handlers": {
                "file": {
                    "class": "logging.handlers.TimedRotatingFileHandler",
                    "filename": log_dir / "app.log",
                    "when": "D",
                    "interval": 1,
                    "backupCount": 7,
                    "formatter": "json",
                },
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "console",
                    "stream": sys.stdout,
                },
            },
            "loggers": {
                # Configure our application's logger
                "src": {
                    "handlers": ["console", "file"],
                    "level": log_level,
                    "propagate": False,  # Do not pass logs to the root logger
                },
            },
        }
    )

    # Configure structlog to wrap the standard library logging
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *shared_processors,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> Any:
    """
    Get a pre-configured structlog logger.
    The name should correspond to the logger configured in `logging.config.dictConfig`.
    Using `__name__` is standard practice.
    """
    return structlog.get_logger(name)
