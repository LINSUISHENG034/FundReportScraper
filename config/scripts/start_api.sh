#!/bin/bash
cd "."
export PATH="$HOME/.local/bin:$PATH"
export PYTHONPATH="$(pwd):$PYTHONPATH"

# 设置开发环境的数据库配置
if [ -f "alembic.dev.ini" ]; then
    export DATABASE_URL="sqlite:///./fund_reports_dev.db"
fi

python3 -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
