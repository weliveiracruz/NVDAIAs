#!/bin/sh
# Runs every test. Needs Linux with python3-wxgtk4.0 and xvfb installed.
set -e
cd "$(dirname "$0")/.."
python3 -m unittest tests/test_pure.py
xvfb-run -a python3 tests/test_gui.py
NVDAIAS_LANG=pt_BR xvfb-run -a python3 tests/test_translation.py
python3 build.py
