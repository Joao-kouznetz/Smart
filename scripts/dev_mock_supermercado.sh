#!/usr/bin/env sh
set -eu

fastapi dev mock_supermercado/main.py --port 8001
