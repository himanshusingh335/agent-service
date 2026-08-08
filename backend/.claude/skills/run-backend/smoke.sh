#!/usr/bin/env bash
# Smoke-drives the backend agent service end-to-end over HTTP/SSE, including
# the task-service MCP tool and the human-in-the-loop approval flow.
# Run from backend/: .claude/skills/run-backend/smoke.sh
set -euo pipefail

BACKEND_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
REPO_ROOT="$(cd "$BACKEND_ROOT/.." && pwd)"
PYTHON="$REPO_ROOT/.venv/bin/python"
TASK_SVC_ROOT="$REPO_ROOT/task-service"

BACKEND_LOG=/tmp/backend-smoke.log
TASK_SVC_LOG=/tmp/task-service-for-backend-smoke.log
TASK_SVC_DB=/tmp/task-service-for-backend-smoke.db

for p in 8000 8010; do
  if lsof -i ":$p" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "ERROR: port $p already in use. Kill the existing process first:" >&2
    lsof -i ":$p" -sTCP:LISTEN >&2
    exit 1
  fi
done

cd "$BACKEND_ROOT"
if [ ! -f .env ]; then
  echo "ERROR: backend/.env missing (needs GROQ_API_KEY). Copy .env.example and fill it in." >&2
  exit 1
fi

echo "=== ensuring Postgres is up ==="
docker compose up -d
for i in $(seq 1 20); do
  if docker compose exec -T postgres pg_isready -U postgres >/dev/null 2>&1; then break; fi
  sleep 1
done

echo "=== starting task-service (provides the MCP task-tracker tool) ==="
rm -f "$TASK_SVC_LOG" "$TASK_SVC_DB"
# Must cd into task-service/ first: pydantic-settings resolves `.env` relative
# to cwd, not the script file, and task-service has no .env of its own — but
# if launched from backend/ it silently picks up backend/.env's PORT=8000 and
# binds there instead of 8010. `exec` keeps $! pointing at the real python
# process (not a subshell) so cleanup can actually kill it.
(
  cd "$TASK_SVC_ROOT"
  exec env DB_PATH="$TASK_SVC_DB" "$PYTHON" src/main.py
) > "$TASK_SVC_LOG" 2>&1 &
TASK_SVC_PID=$!

cleanup() {
  kill "$BACKEND_PID" "$TASK_SVC_PID" 2>/dev/null || true
}
trap cleanup EXIT

# task-service MUST be reachable before backend starts: the agent's lifespan
# loads MCP tools from it at startup and fails the whole app if it can't connect.
for i in $(seq 1 20); do
  if curl -s -o /dev/null "http://localhost:8010/docs"; then break; fi
  sleep 0.5
done

echo "=== starting backend ==="
rm -f "$BACKEND_LOG"
"$PYTHON" src/main.py > "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

for i in $(seq 1 20); do
  if curl -s -o /dev/null "http://localhost:8000/docs"; then break; fi
  sleep 0.5
done

echo "=== backend reachable ==="
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/docs

SID1="smoke-$(date +%s)-basic"
echo "=== /chat/invoke: basic tool call (get_current_date, local tool) ==="
curl -s -X POST http://localhost:8000/chat/invoke -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SID1\",\"message\":\"What is today's date? Answer in one short sentence.\"}"
echo

echo "=== /chat/{session_id}/history ==="
curl -s "http://localhost:8000/chat/$SID1/history"
echo

SID2="smoke-$(date +%s)-hitl"
echo "=== /chat/invoke: add a task via MCP tool (no approval needed) ==="
curl -s -X POST http://localhost:8000/chat/invoke -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SID2\",\"message\":\"add a task called smoke-test-task\"}"
echo

echo "=== /chat/invoke: delete it -> should interrupt for HITL approval ==="
curl -s -X POST http://localhost:8000/chat/invoke -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SID2\",\"message\":\"delete the smoke-test-task task\"}"
echo

echo "=== /chat/resume: approve the pending remove_task ==="
curl -s -X POST http://localhost:8000/chat/resume -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SID2\",\"decisions\":[{\"type\":\"approve\"}]}"
echo

echo "=== /chat/{session_id}/logs (filtered to this session) ==="
curl -s "http://localhost:8000/chat/$SID2/logs?limit=5"
echo

SID3="smoke-$(date +%s)-stream"
echo "=== /chat/stream (SSE) ==="
curl -s -N -X POST http://localhost:8000/chat/stream -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SID3\",\"message\":\"Say the word banana.\"}" --max-time 15
echo

echo "=== backend log tail ==="
tail -15 "$BACKEND_LOG"

echo "smoke test complete"
