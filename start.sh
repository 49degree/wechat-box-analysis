#!/bin/bash
set -e

# Railway 提供 PORT 环境变量，默认 8501
export PORT=${PORT:-8501}

exec streamlit run dashboard.py \
  --server.port "$PORT" \
  --server.address 0.0.0.0 \
  --server.headless true \
  --browser.gatherUsageStats false
