#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null; then
  echo 'Python 3.11+ is required. See README for installation.'
  exit 1
fi
exec python3 scripts/bootstrap.py "$@"
