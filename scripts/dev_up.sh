#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
ENTERPRISE_DIR="$ROOT_DIR/frontend-enterprise"
CHAT_DIR="$ROOT_DIR/frontend-chat"
RUN_DIR="$ROOT_DIR/.dev"
LABEL_PREFIX="com.skill-agent-loop"
OLD_LABEL_PREFIX="com.so""p-agent-loop"

API_BASE_URL="${VITE_API_BASE_URL:-http://127.0.0.1:8000}"

mkdir -p "$RUN_DIR"

remove_label() {
  local name="$1"
  launchctl remove "$OLD_LABEL_PREFIX.$name" >/dev/null 2>&1 || true
  launchctl remove "$LABEL_PREFIX.$name" >/dev/null 2>&1 || true
}

kill_pid_file() {
  local name="$1"
  local pid_file="$RUN_DIR/$name.pid"
  if [[ -f "$pid_file" ]]; then
    local pid
    pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      sleep 0.2
    fi
    rm -f "$pid_file"
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
  fi
}

start_service() {
  local name="$1"
  local cwd="$2"
  local command="$3"
  local log_file="/tmp/skill-agent-$name.log"
  local err_file="/tmp/skill-agent-$name.err.log"
  local pid_file="$RUN_DIR/$name.pid"

  : > "$log_file"
  : > "$err_file"
  launchctl submit \
    -l "$LABEL_PREFIX.$name" \
    -o "$log_file" \
    -e "$err_file" \
    -- /bin/zsh -lc "cd '$cwd' && $command"
  echo "launchctl:$LABEL_PREFIX.$name" > "$pid_file"
}

wait_url() {
  local label="$1"
  local url="$2"
  local log_file="$3"
  for _ in {1..80}; do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.25
  done
  echo "$label failed to become ready: $url" >&2
  echo "Last log lines from $log_file:" >&2
  tail -n 80 "$log_file" >&2 || true
  exit 1
}

for name in backend enterprise chat; do
  remove_label "$name"
  kill_pid_file "$name"
done

sleep 0.5

for port in 8000 5173 5174; do
  kill_port "$port"
done

sleep 0.5

start_service "backend" "$BACKEND_DIR" "exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000"
start_service "enterprise" "$ENTERPRISE_DIR" "export VITE_API_BASE_URL='$API_BASE_URL'; exec ./node_modules/.bin/vite --host 127.0.0.1 --port 5173 --strictPort"
start_service "chat" "$CHAT_DIR" "export VITE_API_BASE_URL='$API_BASE_URL'; exec ./node_modules/.bin/vite --host 127.0.0.1 --port 5174 --strictPort"

wait_url "backend" "http://127.0.0.1:8000/api/health" "/tmp/skill-agent-backend.log"
wait_url "enterprise" "http://127.0.0.1:5173/enterprise/dashboard" "/tmp/skill-agent-enterprise.log"
wait_url "chat" "http://127.0.0.1:5174/chat" "/tmp/skill-agent-chat.log"

echo "Started:"
echo "  backend    http://127.0.0.1:8000/docs"
echo "  enterprise http://127.0.0.1:5173/enterprise/dashboard"
echo "  chat       http://127.0.0.1:5174/chat"
echo
echo "Logs:"
echo "  /tmp/skill-agent-backend.log"
echo "  /tmp/skill-agent-enterprise.log"
echo "  /tmp/skill-agent-chat.log"
