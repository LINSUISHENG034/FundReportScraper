# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Fund Report Scraping and Analysis Platform** (公募基金报告自动化采集与分析平台) for automatically collecting, parsing, and analyzing Chinese public fund reports from the CSRC disclosure platform (eid.csrc.gov.cn).

### Technology Stack (Planned)
- **Backend**: Python 3.10+, FastAPI, SQLAlchemy 2.0
- **Task Queue**: Celery + Redis 
- **Database**: PostgreSQL 14+
- **Storage**: MinIO (S3-compatible object storage)
- **Parsing**: XBRL (arelle library), lxml, beautifulsoup4
- **HTTP Client**: httpx (async support)
- **Logging**: Structlog (mandatory - structured JSON logs)
- **Testing**: Pytest (mandatory - 80%+ coverage requirement)
- **Containerization**: Docker + Docker Compose

### Project Structure (To Be Implemented)

The project will follow a modular architecture:
- **Scheduler**: Celery Beat for automated periodic tasks
- **Workers**: Celery workers for scraping, parsing, and data processing
- **API Layer**: FastAPI endpoints for manual triggers and data queries
- **Core Modules**: Scraper, XBRL parser, data models, storage handlers
- **Monitoring**: Structured logging with contextual information binding

### Development Phases
1. **Phase 1 (W1-W3)**: Infrastructure setup, core scraping functionality
2. **Phase 2 (W4-W6)**: XBRL parsing and database integration  
3. **Phase 3 (W7-W8)**: Task scheduling and error handling
4. **Phase 4 (W9-W10)**: API development and deployment preparation
5. **Phase 5 (W11-W12)**: UAT, historical data backfill, production launch

## Development Commands

**Note**: The project codebase is not yet implemented. These commands are placeholders based on the planned technology stack:

```bash
# Environment setup (planned)
conda activate fund-scraper  # Ensure conda environment is active
pip install -r requirements.txt  # Will use Poetry or similar

# Development (planned)
python -m pytest                 # Run all tests
python -m pytest -v tests/unit/  # Run unit tests only
python -m pytest --cov=src      # Run tests with coverage
python -m black .               # Code formatting
python -m flake8 .              # Linting

# Docker operations (planned) 
docker-compose up -d            # Start development services
docker-compose logs -f          # View logs
docker-compose down             # Stop services

# Celery operations (planned)
celery -A app.celery worker --loglevel=info     # Start worker
celery -A app.celery beat --loglevel=info       # Start scheduler
```

## Mandatory Development Requirements

### Logging (Structlog - REQUIRED)
- **No print() statements allowed** - use structured logging only
- All logs must be JSON format with contextual binding
- Log levels: INFO (business flows), WARNING (recoverable issues), ERROR (task failures), DEBUG (development only)
- Context binding example: `log = log.bind(task_id="abc", fund_code="000001")`

### Testing (Pytest - REQUIRED)  
- **80% minimum coverage** for core business logic
- Unit tests must mock external dependencies (HTTP, database)
- Integration tests for module interactions
- All new features require corresponding test cases

### Data Sources & Targets
- **Primary source**: 资本市场电子化信息披露平台 (eid.csrc.gov.cn)
- **File formats**: XBRL (primary), PDF/HTML (fallback)
- **Key data**: Asset allocation, top 10 holdings, industry distribution
- **Storage**: Raw files in MinIO, structured data in PostgreSQL

# ABSOLUTE PROHIBITIONS
- **NEVER** create new files in root directory → use proper module structure
- **NEVER** write output files directly to root directory → use designated output folders
- **NEVER** create documentation files (.md) unless explicitly requested by user
- **NEVER** use git commands with -i flag (interactive mode not supported)
- **NEVER** use `find`, `grep`, `cat`, `head`, `tail`, `ls` commands → use Read, LS, Grep, Glob tools instead
- **NEVER** create duplicate files or multiple implementations → extend existing files, maintain single source of truth
- **NEVER** copy-paste code blocks → extract into shared utilities/functions
- **NEVER** hardcode values that should be configurable → use config files/environment variables
- **NEVER** persist with fixing compatibility issues beyond 3 similar errors → evaluate technology stack replacement
- **NEVER** assume current technology choices are optimal → question and propose alternatives when patterns of issues emerge
- **NEVER** focus solely on immediate fixes → consider long-term maintenance costs and developer experience

# MANDATORY REQUIREMENTS
- User requires following Python's 'elegant is better than ugly' principle for clean, maintainable, testable code.
- **COMMIT** after every completed task/phase and **PUSH** to GitHub for backup: `git push origin main`
- **USE TASK AGENTS** for all long-running operations (>30 seconds) - Bash commands stop when context switches
- **TODOWRITE** for complex tasks (3+ steps) → parallel agents → git checkpoints → test validation
- **READ FILES FIRST** before editing - Edit/Write tools will fail if you didn't read the file first
- **DEBT PREVENTION** - Before creating new files, check for existing similar functionality to extend
- **CONDA ENVIRONMENT** - Ensure conda environment is activated before installing libraries and update environment.yml
- **TECHNOLOGY EVALUATION** - When encountering 3+ similar compatibility/integration issues, propose alternative technology stacks
- **HOLISTIC COST ANALYSIS** - Consider both immediate implementation costs and long-term maintenance burden in technical decisions
- **PROACTIVE ARCHITECTURE REVIEW** - Question existing technology choices when they consistently create friction or maintenance overhead
- **DEVELOPER EXPERIENCE PRIORITY** - Factor in development efficiency, debugging ease, and team productivity in technology selection

# DEVELOPMENT STRATEGY
1.  **Principle 1: Analyze Before Acting (The "Look Before You Leap" Rule)**
    - **Commitment**: Before creating any new file or module, I **must** first use directory listing tools to thoroughly investigate the existing structure of the target directory and its parents.
    - **Action**: I will actively look for files like `__init__.py`, `base.py`, `utils.py`, `abc.py`, or `interfaces.py` as strong indicators of the project's design intent. I will also examine the naming and organization of sibling directories to infer established patterns.

2.  **Principle 2: Adhere to the Single Responsibility Principle (The "Single Responsibility" Rule)**
    - **Commitment**: Every module I create **must** have a clear, single, and well-defined responsibility.
    - **Action**: When proposing a new module, I must be able to describe its core responsibility in a single sentence. If I find a module taking on multiple unrelated duties, I will proactively propose splitting it into more focused modules.

3.  **Principle 3: Follow Existing Conventions (The "When in Rome" Rule)**
    - **Commitment**: I **must** strictly adhere to and mimic the project's existing code style, naming conventions, and directory structure.
    - **Action**: I will treat project consistency as a top priority. If I see that all service interfaces are defined in `providers/base.py`, I will never propose creating a similar interface file elsewhere. I will actively adopt and perpetuate the project's "dialect" and "culture."

4.  **Principle 4: Propose and Confirm Structural Changes (The "Measure Twice, Cut Once" Rule)**
    - **Commitment**: For all operations that affect the project's file structure (especially **creating, moving, or renaming** files and directories), I **must** first present a clear, justified plan to you and receive your approval before execution.
    - **Action**: I will no longer call `write_file` to create a new module directly. Instead, I will state: "My plan is to create a new file at `path/to/new_module.py` with the responsibility of [X]. I've chosen this location because it follows the existing pattern in the [Y] directory. Do you agree with this approach?"
