# CLAUDE.md

## Repository layout

This repo has three independent Python projects, each with its own `requirements.txt`, sharing the repo-root `.venv`:

- `backend/` — a FastAPI service wrapping a LangGraph/LangChain agent (Groq-hosted LLM), with Postgres-backed conversation checkpointing.
- `tui/` — a minimal terminal client (`rich` + `httpx`) that talks to the backend over HTTP/SSE.
- `task-service/` — a small FastAPI + SQLite task tracker (`add_task`/`remove_task`), self-exposed as an MCP server via `fastapi-mcp` (mounted at `/mcp`, tool names come from each route's `operation_id`). The backend agent consumes it as an MCP tool source — see `backend/mcp_servers.json`.

## Commands

All commands assume `cd` into the relevant subproject first (`backend/` or `tui/`).

### Backend

The project uses a conda-created venv at `.venv` (`conda create -p .venv python=3.11`), managed with pip — not `uv`/`poetry`.

```bash
conda activate ./.venv        # or: source .venv/bin/activate
cd backend
pip install -r requirements.txt
docker compose up -d          # starts Postgres on localhost:5432
python src/main.py            # runs the API (uses .env via pydantic-settings)
```

- Config comes from `backend/.env` (copy from `.env.example`); required var is `GROQ_API_KEY`.
- No test suite or linter is currently configured in this repo.
- MCP tools are optionally loaded from `backend/mcp_servers.json` (gitignored; see `mcp_servers.example.json` for format). If the file is absent, the agent runs with local tools only.

### TUI

```bash
conda activate ./.venv        # or: source .venv/bin/activate
cd tui
pip install -r requirements.txt
python client/main.py         # connects to AGENT_SERVICE_URL (default http://localhost:8000)
```

### Task service

```bash
conda activate ./.venv        # or: source .venv/bin/activate
cd task-service
pip install -r requirements.txt
python src/main.py            # runs on http://localhost:8010, SQLite file at settings.db_path
```

Start this before the backend if you want `add_task`/`remove_task` tools available — `backend/mcp_servers.json` points at it by default.

