---
name: run-backend
description: Build, run, and smoke-test the backend agent service — FastAPI wrapping a LangGraph/LangChain agent (Groq LLM), Postgres checkpointing, MCP tool loading, SSE streaming, and human-in-the-loop tool approval. Use when asked to run, start, launch, test, or verify the backend, or to check /chat/invoke, /chat/stream, /chat/resume, history, or logs endpoints.
---

Paths below are relative to `backend/` (this skill's grandparent directory).

The backend has no GUI/TUI of its own — it's an HTTP+SSE API — so it's
driven with `curl`. The interesting behavior (MCP tool loading, the
human-in-the-loop approval interrupt) only shows up when it's exercised
through a real request flow, not just `GET /docs`.

## Prerequisites

Shared repo-root venv at `../.venv` (conda-created, pip-managed):

```bash
cd .. && conda activate ./.venv   # or: source ../.venv/bin/activate
cd backend
pip install -r requirements.txt
```

Needs `backend/.env` (copy from `.env.example`) with a real `GROQ_API_KEY` —
there is no offline/mock mode; every chat turn calls the live Groq API.
Needs Docker for Postgres (`docker compose up -d`, `docker-compose.yml` in
this directory).

## Run (agent path) — smoke.sh

```bash
.claude/skills/run-backend/smoke.sh
```

This is the primary way to drive the app. It:
1. Refuses to run if ports 8000 or 8010 are already bound.
2. Errors out early if `.env` is missing.
3. Runs `docker compose up -d` and waits for Postgres to be ready.
4. Starts **task-service** first (it provides the `task-tracker` MCP tool
   the backend loads at startup — see Gotchas for why this has to happen
   first and from the right directory), then polls it healthy.
5. Starts the backend, polls `/docs` healthy.
6. Drives every endpoint with a real conversation:
   - `POST /chat/invoke` with a prompt that forces the local
     `get_current_date` tool.
   - `GET /chat/{session_id}/history` to check the tool-call/tool-result
     messages got persisted correctly.
   - `POST /chat/invoke` asking the agent to add a task (exercises the MCP
     `add_task` tool, no approval gate).
   - `POST /chat/invoke` asking it to delete that task — this must come
     back with `pending_actions` (the `remove_task` tool is gated by
     `HumanInTheLoopMiddleware`), not a `reply`.
   - `POST /chat/resume` with `{"type":"approve"}` to complete the delete.
   - `GET /chat/{session_id}/logs` to confirm session-scoped log retrieval
     works and includes `role`/`content` on transcript entries.
   - `POST /chat/stream` (SSE) for a one-word reply.
7. Tails the backend log and kills both background processes on exit
   (trap), success or failure.

Verified output (this session, trimmed):

```
=== backend reachable ===
200
=== /chat/invoke: basic tool call (get_current_date, local tool) ===
{"session_id":"smoke-...-basic","reply":"Today's date is 2026-08-08.","pending_actions":null}
=== /chat/invoke: delete it -> should interrupt for HITL approval ===
{"session_id":"smoke-...-hitl","reply":null,"pending_actions":[{"name":"remove_task","args":{"task_id":1},"description":"This will permanently delete the task. Approve?"}]}
=== /chat/resume: approve the pending remove_task ===
{"session_id":"smoke-...-hitl","reply":"Task 1 deleted.","pending_actions":null}
=== /chat/stream (SSE) ===
data: banana
```

To drive it manually instead of via the script:

```bash
docker compose up -d
(cd ../task-service && ../.venv/bin/python src/main.py) &   # must run from task-service/, see Gotchas
../.venv/bin/python src/main.py &                            # from backend/
curl -s -X POST http://localhost:8000/chat/invoke -H "Content-Type: application/json" \
  -d '{"session_id":"s1","message":"add a task called foo"}'
```

## Run (human path)

```bash
docker compose up -d
python src/main.py   # http://localhost:8000, reads backend/.env
```

Foreground process, `Ctrl-C` to stop. Same as the agent path minus the
scripted request sequence — you'd need a TUI or curl session to actually
talk to it (see `tui/.claude/skills/run-tui/` for the interactive client).

## Gotchas

- **task-service must be launched with its cwd set to `task-service/`, not
  `backend/`.** `pydantic-settings` resolves `env_file=".env"` relative to
  the process's *current working directory*, not the script's location.
  task-service ships no real `.env` (only `.env.example`), so if you launch
  it from `backend/` (which does have a `.env` with `PORT=8000`), it
  silently loads backend's `.env` and binds to port **8000** instead of
  8010 — collides with backend, whose own `/chat/*` routes then 404
  because you're actually talking to task-service's app. This happened
  live while building `smoke.sh`: backend "was reachable" (200 on `/docs`)
  but every `/chat/*` call returned `{"detail":"Not Found"}`, because
  `/docs` was task-service's docs page, not the agent's.
- **task-service must be up before the backend starts**, not just
  eventually. The backend's app-factory lifespan loads MCP tools from
  `mcp_servers.json` synchronously at startup; if task-service isn't
  reachable yet, backend startup raises and the whole app fails (still
  binds the port in some failure modes, giving misleading `200`s on
  unrelated stale processes — always check `lsof -i :PORT` if behavior
  looks wrong).
- **Backgrounding with `(cd dir && cmd) &` doesn't give you a killable
  PID.** `$!` after that pattern points at the subshell, and on this
  system the subshell forked rather than exec'd into the final command
  (likely because of the `VAR=value cmd` prefix), so `kill $!` in a
  cleanup trap silently no-ops and leaks the process. Fix: `(cd dir &&
  exec env VAR=value cmd) &` — the explicit `exec` replaces the subshell,
  so `$!` is the real process.
- The `remove_task` interrupt round-trip needs the *same* `session_id` on
  both the triggering `/chat/invoke` and the `/chat/resume` call — the
  pending state lives in the LangGraph checkpointer keyed by
  `thread_id = session_id`.

## Troubleshooting

- `{"detail":"Not Found"}` on every `/chat/*` route despite `/docs`
  returning 200 — you're talking to task-service, not the backend (see
  Gotchas). Check `curl http://localhost:8000/openapi.json` — if the
  paths are `/tasks` and `/tasks/{task_id}`, that's task-service.
- Backend log full of `httpx.ConnectError: All connection attempts
  failed` right after startup — task-service wasn't up yet when the
  backend's lifespan tried to load MCP tools. Start task-service first
  and poll it healthy before starting the backend.
- `curl` hangs on `/chat/invoke` — check Groq API reachability/API key;
  every turn makes a live call to `https://api.groq.com`.
