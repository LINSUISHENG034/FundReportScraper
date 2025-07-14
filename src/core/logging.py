"""
Structured logging configuration using structlog.
强制要求：所有日志必须使用structlog，禁止使用print()语句。
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Any, Dict

import structlog
from structlog.types import Processor


def add_app_context(logger: Any, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Add application context to log entries."""
    event_dict["app"] = "fund-report-scraper"
    event_dict["version"] = "0.1.0"
    return event_dict


from src.core.config import settings

def configure_logging(log_level: str = settings.logging.level) -> None:
    """
    Configure structured logging with JSON output.
    
    Args:
        
    """
    # Configure structlog processors
    log_level = log_level.upper()
    json_logs = settings.logging.json_format
    log_dir = Path(settings.logging.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"

    # Configure structlog processors
    processors: list[Processor] = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        add_app_context,
        structlog.processors.format_exc_info,
    ]

    if json_logs:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    # Setup handlers
    handler = logging.handlers.TimedRotatingFileHandler(log_file, when="D", interval=1, backupCount=7)
    handler.setFormatter(logging.Formatter("%(message)s"))

    # Configure standard library logging to use this handler
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging



def get_logger(name: str = "") -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Configured structured logger
        
    Example:
        >>> log = get_logger(__name__)
        >>> log = log.bind(task_id="abc-123", fund_code="000001")
        >>> log.info("task.started", report_type="ANNUAL")
    """
    return structlog.get_logger(name)


# Pre-configured logger instance
logger = get_logger("fund_scraper")