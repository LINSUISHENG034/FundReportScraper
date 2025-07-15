# Phase 5 Guidance: Global Standardization

## 1. Objective

This is the final phase of our refactoring effort. The goal is to elevate the project to a production-ready state by enforcing project-wide standards for logging, code style, and testing. Completing this phase will ensure the codebase is clean, maintainable, and robust.

## 2. Task 1: Unified Logging with `Structlog`

Consistent, structured logging is crucial for monitoring and debugging in a production environment. We will replace all remaining `print()` and standard `logging` calls with our configured `structlog` logger.

### Step 1.1: Finalize Logging Configuration

The current logging configuration in `src/core/logging.py` will be replaced with a more robust, production-grade setup. The new configuration will:
- Log JSON-formatted output to a rotating file.
- **Also** print human-readable, colored logs to the console (ideal for development).
- Avoid polluting the root logger, only capturing logs from our application (`fund-report-scraper`).

**Action**: Replace the entire content of `src/core/logging.py` with the following code:

```python
# src/core/logging.py
import logging
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
    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False, # Keep third-party loggers
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
                "propagate": False, # Do not pass logs to the root logger
            },
        }
    })

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

```

### Step 1.2: Global Replacement of Logging Calls

Now, the development team must systematically go through the entire `src/` directory and replace all instances of `print()` and `logging.info()` with calls to our new logger.

**How to get a logger**:
At the top of any file that needs logging, add:
```python
from src.core.logging import get_logger
logger = get_logger(__name__)
```

**How to log**:
The key is to log events with context, not just strings.

**Before**:
```python
print(f"Starting download for {fund_code}")
# or
logging.info(f"Starting download for {fund_code}")
```

**After**:
```python
# Good: Log an event with context
logger.info("download.started", fund_code=fund_code)

# Better: Bind context that will be present in all subsequent logs
bound_logger = logger.bind(fund_code=fund_code, task_id="xyz")
bound_logger.info("download.started")
# ... later ...
bound_logger.info("download.success", file_size=12345)
```

**Target Files**: Systematically check and update all files in:
- `src/api/`
- `src/core/`
- `src/models/`
- `src/parsers/`
- `src/scrapers/`
- `src/services/`
- `src/tasks/`
- `src/utils/`
- `src/cli.py`, `src/main.py`

## 3. Task 2: Code Style Unification

To ensure a consistent and readable codebase, we will use `black` for formatting and `flake8` for linting.

**Action**: From the project's root directory, run the following commands in order:

1.  **Format the code with `black`**:
    ```bash
    poetry run black .
    ```
    This command will automatically reformat all Python files.

2.  **Check for style issues with `flake8`**:
    ```bash
    poetry run flake8 src tests
    ```
    This command will report any remaining style violations or potential bugs. The team must fix all reported issues until this command runs silently with no output.

## 4. Task 3: Final Verification & Coverage Check

This is the final quality gate. We will run the entire test suite and generate a code coverage report.

**Action**: From the project's root directory, run the following command:
```bash
poetry run pytest --cov=src --cov-report=html
```

**Success Criteria**:
1.  **All tests must pass.**
2.  Open the generated coverage report at `htmlcov/index.html` in a web browser.
3.  The **Total Coverage** percentage must be **greater than 80%**.

If coverage is below 80%, the team should identify critical functions or modules that are not tested and write the necessary unit or integration tests to meet the target.

## 5. Definition of Done

Phase 5 is considered complete when:
- [ ] The new logging configuration is implemented.
- [ ] All `print` and `logging` calls in `src/` have been replaced with `structlog`.
- [ ] `poetry run black .` runs without making changes.
- [ ] `poetry run flake8 src tests` runs without reporting any errors.
- [ ] `poetry run pytest --cov=src` passes with >80% coverage.
- [ ] A final Pull Request containing all these changes has been reviewed and merged.

This concludes the refactoring roadmap. Upon completion, the project will be in a significantly healthier and more maintainable state.
