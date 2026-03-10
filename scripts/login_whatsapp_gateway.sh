#!/bin/zsh

set -euo pipefail

ROOT="/Users/harshbhatt/Projects/soul"
cd "$ROOT/gateway"

exec npm run login
