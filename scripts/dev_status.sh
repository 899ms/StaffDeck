#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT_DIR/.dev"
LABEL_PREFIX="com.skill-agent-loop"
OLD_LABEL_PREFIX="com.so""p-agent-loop"

echo "Processes:"
for name in backend enterprise chat; do
  if launchctl list "$LABEL_PREFIX.$name" >/dev/null 2>&1; then
    echo "  $name launchctl registered"
  elif launchctl list "$OLD_LABEL_PREFIX.$name" >/dev/null 2>&1; then
    echo "  $name old launchctl registered"
  else
    pid_file="$RUN_DIR/$name.pid"
    if [[ -f "$pid_file" ]]; then
      pid="$(cat "$pid_file" 2>/dev/null || true)"
      if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
        echo "  $name running ($pid)"
      else
        echo "  $name stale pid"
      fi
    else
      echo "  $name not started"
    fi
  fi
done
echo

echo "Ports:"
for port in 8000 5173 5174; do
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "  $port listening"
  else
    echo "  $port not listening"
  fi
done
echo

echo "Health:"
curl -sS http://127.0.0.1:8000/api/health || true
echo
