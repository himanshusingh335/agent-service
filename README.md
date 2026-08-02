# agent-service

A FastAPI service wrapping a LangGraph/LangChain agent (Groq-hosted LLM) with Postgres-backed
conversation checkpointing, plus a terminal client (TUI) to talk to it.

## Layout

- `backend/` — the agent API (FastAPI + LangGraph + Postgres).
- `tui/` — a terminal chat client (`rich` + `httpx`).

Both use a single conda-created virtualenv at the repo root (`.venv`), managed with `pip`.

## Setup

```bash
conda create -p .venv python=3.11
conda activate ./.venv
```

## Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env          # fill in GROQ_API_KEY
docker compose up -d          # starts Postgres on localhost:5432
python src/main.py            # runs the API on http://localhost:8000
```

Optional: to give the agent MCP tools, copy `mcp_servers.example.json` to `mcp_servers.json` and
configure your servers (see the file for the format). If it's absent, the agent runs with local
tools only.

## TUI

```bash
cd tui
pip install -r requirements.txt
cp .env.example .env          # set AGENT_SERVICE_URL if not http://localhost:8000
python client/main.py
```

On startup you'll be prompted to choose a response mode:

- `stream` (default) — tokens are printed as they arrive over SSE.
- `invoke` — the full reply is printed at once.

Type `/mode` at any time to switch modes mid-session, and `exit`/`quit` to leave.

## Logs

The backend writes structured JSON logs to `backend/logs/app.log` (and stdout), tagged with the
request's `session_id`. Conversation turns (human/ai/tool messages) are logged with a `role`
field, so you can filter them out with [`jq`](https://jqlang.org/):

```bash
# run the API and show only conversation messages live
python src/main.py 2>&1 | jq -R -r 'fromjson? | select(.role) | "\(.role): \(.content)"'

# only conversation messages, formatted as "role: content"
jq -r 'select(.role) | "\(.role): \(.content)"' backend/logs/app.log

# live tail
tail -f backend/logs/app.log | jq -r 'select(.role) | "\(.role): \(.content)"'

# one session only
jq -r --arg sid "<session-id>" \
  'select(.role and .session_id == $sid) | "\(.role): \(.content)"' \
  backend/logs/app.log
```
