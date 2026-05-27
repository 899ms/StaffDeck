#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT_DIR/.dev"
LABEL_PREFIX="com.skill-agent-loop"
OLD_LABEL_PREFIX="com.so""p-agent-loop"

remove_label() {
  local name="$1"
  launchctl remove "$OLD_LABEL_PREFIX.$name" >/dev/null 2>&1 || true
  if launchctl remove "$LABEL_PREFIX.$name" >/dev/null 2>&1; then
    echo "Stopped launchctl service $name"
  fi
}

kill_pid_file() {
  local name="$1"
  local pid_file="$RUN_DIR/$name.pid"
  if [[ -f "$pid_file" ]]; then
    local pid
    pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      echo "Stopped $name ($pid)"
    else
      echo "$name pid was stale"
    fi
    rm -f "$pid_file"
  else
    echo "$name was not running"
  fi
}

kill_port() {
  local port="$1"
  local pids
  pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    while read -r pid; do
      [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true
    done <<< "$pids"
    echo "Released port $port"
  fi
}

for name in backend enterprise chat; do
  remove_label "$name"
  kill_pid_file "$name"
done

for port in 8000 5173 5174; do
  kill_port "$port"
done
