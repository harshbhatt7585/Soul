#!/bin/zsh

set -euo pipefail

ROOT="/Users/harshbhatt/Projects/soul"
LOG_DIR="$ROOT/.soul/logs"

mkdir -p "$LOG_DIR"
cd "$ROOT"

exec "$ROOT/.venv/bin/python3" "$ROOT/scripts/run_cli_prompts.py" >> "$LOG_DIR/run_cli_prompts.cron.log" 2>&1
