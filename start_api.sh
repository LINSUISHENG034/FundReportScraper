#!/bin/bash
# 获取项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
export PATH="$HOME/.local/bin:$PATH"
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"
python3 -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
