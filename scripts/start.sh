#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python3}"
"$PYTHON" -c 'import sys; assert sys.version_info >= (3,11), "Python 3.11 or newer is required"'
[ -d .venv ] || "$PYTHON" -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m playwright install chromium
printf '\nFrameport is starting at http://127.0.0.1:8040\n\n'
exec python -m frameport.cli
