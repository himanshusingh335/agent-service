#!/usr/bin/env bash
# Drives the TUI end-to-end under tmux: starts task-service + backend,
# launches the TUI, scripts a full chat + HITL-approval + logs/session
# session, and captures the pane at each step for inspection.
# Run from tui/: .claude/skills/run-tui/driver.sh
set -euo pipefail

TUI_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
REPO_ROOT="$(cd "$TUI_ROOT/.." && pwd)"
PYTHON="$REPO_ROOT/.venv/bin/python"
BACKEND_ROOT="$REPO_ROOT/backend"
TASK_SVC_ROOT="$REPO_ROOT/task-service"

TMUX="${TMUX_BIN:-tmux}"
if ! command -v "$TMUX" >/dev/null 2>&1; then
  echo "ERROR: tmux not found. Install it: brew install tmux" >&2
  exit 1
fi

SESSION=tui_driver
TASK_SVC_LOG=/tmp/task-service-for-tui.log
TASK_SVC_DB=/tmp/task-service-for-tui.db
BACKEND_LOG=/tmp/backend-for-tui.log
CAPTURE=/tmp/tui-driver-capture.txt

for p in 8000 8010; do
  if lsof -i ":$p" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "ERROR: port $p already in use. Kill the existing process first:" >&2
    lsof -i ":$p" -sTCP:LISTEN >&2
    exit 1
  fi
done

if [ ! -f "$BACKEND_ROOT/.env" ]; then
  echo "ERROR: backend/.env missing (needs GROQ_API_KEY). Copy .env.example and fill it in." >&2
  exit 1
fi

cd "$BACKEND_ROOT" && docker compose up -d >/dev/null
for i in $(seq 1 20); do
  if docker compose exec -T postgres pg_isready -U postgres >/dev/null 2>&1; then break; fi
  sleep 1
done

echo "=== starting task-service ==="
rm -f "$TASK_SVC_LOG" "$TASK_SVC_DB"
# cd into task-service/ first: pydantic-settings resolves .env relative to
# cwd, and task-service has no .env of its own — launched from elsewhere it
# would silently inherit backend's .env (PORT=8000) and collide with backend.
(
  cd "$TASK_SVC_ROOT"
  exec env DB_PATH="$TASK_SVC_DB" "$PYTHON" src/main.py
) > "$TASK_SVC_LOG" 2>&1 &
TASK_SVC_PID=$!

cleanup() {
  "$TMUX" kill-session -t "$SESSION" 2>/dev/null || true
  kill "$BACKEND_PID" "$TASK_SVC_PID" 2>/dev/null || true
}
trap cleanup EXIT

for i in $(seq 1 20); do
  if curl -s -o /dev/null "http://localhost:8010/docs"; then break; fi
  sleep 0.5
done

echo "=== starting backend ==="
rm -f "$BACKEND_LOG"
(
  cd "$BACKEND_ROOT"
  exec "$PYTHON" src/main.py
) > "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

for i in $(seq 1 20); do
  if curl -s -o /dev/null "http://localhost:8000/docs"; then break; fi
  sleep 0.5
done

echo "=== launching TUI under tmux ==="
"$TMUX" kill-session -t "$SESSION" 2>/dev/null || true
"$TMUX" new-session -d -s "$SESSION" -x 200 -y 50
"$TMUX" send-keys -t "$SESSION" "cd '$TUI_ROOT' && AGENT_SERVICE_URL=http://localhost:8000 '$PYTHON' client/main.py" Enter
sleep 2

send() { "$TMUX" send-keys -t "$SESSION" "$1" Enter; sleep "${2:-1.5}"; }

send "chat"
send "invoke"
send "add a task called tui-smoke-task" 4
send "delete the tui-smoke-task task" 4
send "y" 3
send "exit"
send "session"
SID=$("$TMUX" capture-pane -t "$SESSION" -p | grep -oE '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' | tail -1)
echo "captured session id: $SID"
send "$SID" 2
send "logs"
send "$SID" 1
send "" 1     # level: blank
send "" 1     # start_time: blank
send "" 1     # end_time: blank
send "20" 2   # limit

echo "=== final pane capture ==="
"$TMUX" capture-pane -t "$SESSION" -p | tee "$CAPTURE"
echo
echo "full capture saved to $CAPTURE"

# Exit the TUI cleanly, then the driven shell — capture happens above,
# before the pane's process count drops to zero (which would tear down
# the whole tmux server if this is its only session).
send "exit"
send "exit" 1
