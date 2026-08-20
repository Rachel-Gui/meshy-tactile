#!/bin/zsh
set -e

cd /Users/a0000/Desktop/tactile
exec /Users/a0000/anaconda3/bin/python -m uvicorn web.server.app:app \
  --host 127.0.0.1 \
  --port 8001
