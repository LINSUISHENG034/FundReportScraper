#!/bin/bash

# Run tests with coverage report
# 运行测试并生成覆盖率报告

set -e

echo "🧪 Running tests with coverage..."

# Ensure we're in project root
cd "$(dirname "$0")"

# Check if poetry is available
if command -v poetry &> /dev/null; then
    echo "Using Poetry to run tests..."
    poetry run pytest -v --cov=src --cov-report=term-missing --cov-report=html
else
    echo "Using direct pytest..."
    python -m pytest -v --cov=src --cov-report=term-missing --cov-report=html
fi

echo "✅ Tests completed!"
echo "📊 Coverage report generated in htmlcov/index.html"