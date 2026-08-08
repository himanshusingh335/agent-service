---
name: run-task-service
description: Build, run, and smoke-test task-service — the FastAPI + SQLite task tracker (add_task/remove_task) self-exposed as an MCP server at /mcp. Use when asked to run, start, launch, test, or verify task-service, or to check its HTTP or MCP endpoints work.
---

Paths below are relative to `task-service/` (this skill's grandparent directory).

task-service is a small FastAPI app backed by SQLite, with `fastapi-mcp`
mounting the same routes as an MCP server at `/mcp` (tool names are each
route's `operation_id`: `add_task`, `remove_task`). It's driven over plain
HTTP — no GUI, no TUI — so the harness is a `curl`-based smoke script.

## Prerequisites

Shared repo-root venv at `../.venv` (conda-created, pip-managed — not
uv/poetry). From a clean checkout:

```bash
cd .. && conda create -p .venv python=3.11   # only if .venv doesn't exist
conda activate ./.venv
cd task-service
pip install -r requirements.txt
```

Verified installed at `../.venv/bin/python` in this container; no OS
packages needed (pure Python + SQLite, no native deps to fight).

## Run (agent path) — smoke.sh

```bash
.claude/skills/run-task-service/smoke.sh
```

This is the primary way to drive the app. It:
1. Refuses to run if port 8010 is already bound (prints the conflicting
   process via `lsof` and exits 1 — don't skip this, see Gotchas).
2. Launches `src/main.py` in the background with `DB_PATH` pointed at a
   throwaway `/tmp/task-service-smoke.db` (never touches the real
   `task-service/tasks.db`), polling `/docs` until it's up.
3. Exercises the full flow: `POST /tasks` (add_task) x2, `DELETE
   /tasks/{id}` (remove_task) on a real id and a missing one (expect 404),
   and an MCP `initialize` handshake against `/mcp`.
4. Tails the server log and kills the background process on exit (trap),
   whether the script succeeds or fails.

Verified output (this session):

```
started task-service pid=23131, waiting for startup...
=== docs reachable ===
200
=== add_task: buy milk ===
{"id":1,"title":"buy milk","created_at":"2026-08-08T03:38:59.442157+00:00"}
=== add_task: walk dog ===
{"id":2,"title":"walk dog","created_at":"2026-08-08T03:38:59.454488+00:00"}
=== remove_task: id=1 (should succeed) ===
{"id":1,"deleted":true}
=== remove_task: id=999 (should 404) ===
{"detail":"task not found"} [http 404]
=== MCP initialize handshake ===
{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05","capabilities":{"experimental":{},"tools":{"listChanged":false}},"serverInfo":{"name":"task-service","version":"1.29.0"}}}
```

To drive it manually instead of via the script, the pattern is:

```bash
DB_PATH=/tmp/scratch.db ../.venv/bin/python src/main.py &   # from task-service/
curl -s -X POST http://localhost:8010/tasks -H "Content-Type: application/json" -d '{"title":"buy milk"}'
curl -s -X DELETE http://localhost:8010/tasks/1
```

## Run (human path)

```bash
python src/main.py   # runs on http://localhost:8010, uses ./tasks.db
```

Foreground process; `Ctrl-C` to stop. Uses the real `tasks.db` in this
directory (not throwaway) — fine for manual poking, but prefer `smoke.sh`
for anything you want to leave no trace of.

## Gotchas

- **Port-conflict false negatives are the #1 failure mode here.** If you
  `pkill -f "task-service/src/main.py"` to clean up a previous run, it
  silently does nothing — the process's actual argv is `python src/main.py`
  (relative path, no `task-service/` prefix) once you've `cd`'d into the
  directory, so the pattern never matches. The old server keeps running on
  :8010, and your "new" run's curl output is actually coming from the
  stale process (this happened live in this session — a second run showed
  task ids continuing from a previous run's DB, tracing back to an
  never-killed pid). Use `lsof -i :8010 -sTCP:LISTEN` or `pkill -f
  "src/main.py"` (no path prefix) to actually find/kill it. `smoke.sh`
  checks the port up front specifically to catch this.
- `DB_PATH` env var overrides `.env`'s `DB_PATH=tasks.db` correctly
  (pydantic-settings precedence: env > .env file) — use it to keep smoke
  runs from polluting the real dev DB.
- The MCP endpoint requires **both** `Content-Type: application/json` and
  `Accept: application/json, text/event-stream` headers — omitting
  `Accept` gets a non-JSON error response from the MCP transport layer.

## Troubleshooting

- `curl: (7) Failed to connect` on `/docs` right after launch — startup
  takes ~1-2s; `smoke.sh` polls up to 10s before giving up. If it still
  fails, check the log file (`/tmp/task-service-smoke.log`) for an
  import/port error.
- Unexpected task ids (e.g. starting at 3 instead of 1) on a "fresh" run —
  see the port-conflict gotcha above; you're talking to a stale process
  and its old DB, not your new one.
