#!/bin/bash
cd "$(dirname "$0")"
echo "🍕 Gabin Community Manager"
echo "→ http://localhost:8000"
export PATH="$HOME/Library/Python/3.9/bin:$PATH"
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
