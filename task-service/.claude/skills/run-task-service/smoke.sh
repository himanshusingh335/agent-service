#!/usr/bin/env bash
# Smoke-drives task-service end-to-end over HTTP + MCP.
# Run from task-service/: .claude/skills/run-task-service/smoke.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PYTHON="$ROOT/../.venv/bin/python"
LOG=/tmp/task-service-smoke.log
DB=/tmp/task-service-smoke.db
PORT=8010

if lsof -i ":$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "ERROR: port $PORT already in use. Kill the existing process first:" >&2
  lsof -i ":$PORT" -sTCP:LISTEN >&2
  exit 1
fi

rm -f "$LOG" "$DB"
cd "$ROOT"
DB_PATH="$DB" "$PYTHON" src/main.py > "$LOG" 2>&1 &
PID=$!
echo "started task-service pid=$PID, waiting for startup..."

for i in $(seq 1 20); do
  if curl -s -o /dev/null "http://localhost:$PORT/docs"; then
    break
  fi
  sleep 0.5
done

cleanup() { kill "$PID" 2>/dev/null || true; }
trap cleanup EXIT

echo "=== docs reachable ==="
curl -s -o /dev/null -w "%{http_code}\n" "http://localhost:$PORT/docs"

echo "=== add_task: buy milk ==="
curl -s -X POST "http://localhost:$PORT/tasks" -H "Content-Type: application/json" -d '{"title":"buy milk"}'
echo

echo "=== add_task: walk dog ==="
curl -s -X POST "http://localhost:$PORT/tasks" -H "Content-Type: application/json" -d '{"title":"walk dog"}'
echo

echo "=== remove_task: id=1 (should succeed) ==="
curl -s -X DELETE "http://localhost:$PORT/tasks/1"
echo

echo "=== remove_task: id=999 (should 404) ==="
curl -s -w " [http %{http_code}]" -X DELETE "http://localhost:$PORT/tasks/999"
echo

echo "=== MCP initialize handshake ==="
curl -s -X POST "http://localhost:$PORT/mcp" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"smoke","version":"1.0"}}}' \
  --max-time 5
echo

echo "=== server log tail ==="
tail -10 "$LOG"

echo "smoke test complete"
