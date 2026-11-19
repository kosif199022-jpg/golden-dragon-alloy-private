#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 kosif.py install --group "${1:-own-video}" --execute
