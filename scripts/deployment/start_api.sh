#\!/bin/bash
cd "$(dirname "$0")"  
export PATH="$HOME/.local/bin:$PATH"
export PYTHONPATH="$(pwd):$PYTHONPATH"
python3 -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
