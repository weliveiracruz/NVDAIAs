#!/bin/sh
# Same as: python3 tests/run_all.py  (kept for convenience)
cd "$(dirname "$0")/.." && exec python3 tests/run_all.py "$@"
