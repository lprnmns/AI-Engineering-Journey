#!/usr/bin/env bash

set -euo pipefail

echo "Running Week 2 checks..."
echo

echo "1) OOP DailyLog demo"
python examples/w2d1_daily_log_demo.py
echo

echo "2) Type checking demo"
python examples/w2d2_type_check_demo.py
echo

echo "3) Matrix multiplication demo"
python labs/lin_alg/matrix.py
echo

echo "4) Matrix benchmark"
python labs/lin_alg/matrix_benchmark.py
echo

echo "5) Unit tests"
pytest -v
echo

echo "6) Static type checking"
mypy src examples tests labs projects
echo

echo "Week 2 checks completed."
