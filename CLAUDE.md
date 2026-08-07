# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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

## Architecture

### Backend request flow

`src/main.py` runs uvicorn against `api.app:create_app` (factory pattern). `create_app`'s `lifespan` builds one shared agent instance at startup and stores it on `app.state.agent` — the agent is a singleton per process, not per-request or per-session. `api/deps.get_agent` just reads it off `request.app.state`.

Session/conversation identity is entirely handled by LangGraph's checkpointer, keyed by `thread_id = session_id` (see `_config()` in `api/routes/chat.py`). The API itself is stateless; all conversation history lives in Postgres via `agent/checkpointer.py` (`AsyncPostgresSaver`).

`agent/graph.py` (`build_agent`) assembles the agent per app lifespan:
- Model: `ChatGroq` (model name from `settings.groq_model`).
- Tools: `LOCAL_TOOLS` (currently just `get_current_date` in `agent/tools.py`) concatenated with tools loaded dynamically from MCP servers (`agent/mcp.py::load_mcp_tools`, via `langchain-mcp-adapters`).
- Middleware: `SummarizationMiddleware` (`agent/middleware.py`) trims/summarizes history, keeping the last `settings.summarization_keep_messages` messages. `HumanInTheLoopMiddleware` is deliberately not wired in yet — see the comment in `middleware.py` for how to add tool-approval gating when a tool needs it.
- Built with `langchain.agents.create_agent`, so it's a prebuilt LangGraph agent graph, not a hand-rolled graph.

`/chat/invoke` (non-streaming) and `/chat/stream` (SSE) in `api/routes/chat.py` both: read prior state length via `agent.aget_state`, run the agent (`ainvoke` or `astream_events`), then diff-log only the newly appended messages via `agent/transcript.py::log_new_messages`. This before/after-length diffing pattern is how the transcript logger avoids re-logging history on every turn — replicate it if adding new endpoints that mutate conversation state.

`/chat/{session_id}/logs` (`api/routes/logs.py`) is a stub (501) — log retrieval by session isn't implemented yet, even though logs are already tagged with `session_id` (see below).

### Logging

`core/logging.py` configures a JSON-line logger (console + rotating file at `settings.log_dir/settings.log_file`) with every record tagged by the current `session_id`. `session_id_var` is a `ContextVar` set at the top of each chat request handler (`api/routes/chat.py`) and reset in a `finally` block — any new async code path that logs during a request must set/reset this var the same way, or logs will inherit whatever session_id was last set (or `"-"`).

### Configuration

`core/config.py` defines a single `pydantic-settings` `Settings` object (`settings`), loaded once at import time from `backend/.env`. There is no per-environment settings split — add new config fields directly to this class.

### TUI

`tui/client/api_client.py` (`AgentServiceClient`) is a thin synchronous httpx wrapper; `stream()` parses raw SSE `data:` lines itself rather than using an SSE client library. `tui/client/main.py` is a REPL loop with one session id (a fresh `uuid4`) per process run — there's no session persistence or resumption on the TUI side.
