---
name: run-tui
description: Build, run, and drive the agent-service TUI — the rich/httpx terminal client with a chat/logs/session menu. Use when asked to run, start, launch, test, or screenshot the TUI, or to verify its chat streaming, human-in-the-loop approval prompts, session history view, or log viewer.
---

Paths below are relative to `tui/` (this skill's grandparent directory).

The TUI is an interactive terminal app (`rich` + `httpx`, driven by
`Prompt.ask`), so it's driven with a **tmux wrapper**: `send-keys` to type
into it, `capture-pane` to read what it rendered. It needs the backend (and
task-service, for MCP tools) running first — it has no standalone mode.

## Prerequisites

```bash
cd .. && conda activate ./.venv   # or: source ../.venv/bin/activate
cd tui
pip install -r requirements.txt
brew install tmux   # only if not already installed; verified working at 3.7b
```

Also needs `backend/.env` with a real `GROQ_API_KEY`, and Docker for the
backend's Postgres — see `backend/.claude/skills/run-backend/SKILL.md`.

## Run (agent path) — driver.sh

```bash
.claude/skills/run-tui/driver.sh
```

This is the primary way to drive the app. It:
1. Refuses to run if ports 8000/8010 are already bound.
2. Brings up Postgres, task-service, then the backend (in that order — see
   `run-backend`'s Gotchas on `.env` cwd-resolution and startup ordering,
   which apply identically here).
3. Launches the TUI in a detached tmux session (`tui_driver`, 200x50).
4. Scripts a full interactive session via `tmux send-keys`:
   `chat` → `invoke` mode → add a task (exercises the MCP `add_task` tool)
   → ask to delete it (triggers the `remove_task` HITL interrupt) → `y` to
   approve → `exit` back to the menu → `session` to replay history →
   `logs` to view the session's filtered, role-labeled log lines.
5. Captures the pane with `tmux capture-pane -p` after the last step (to
   `/tmp/tui-driver-capture.txt`) — **before** exiting the TUI, since
   letting the pane's last process exit while it's tmux's only session
   kills the whole server (hit this live, see Gotchas).
6. Tears down: exits the TUI, kills the tmux session, kills backend and
   task-service (trap on exit, runs on success or failure).

Verified output (this session, end of capture):

```
ai: Task ID 1 deleted.

What would you like to do? [chat/logs/session/exit] (chat): logs
session id: 6937595f-...
...
2026-08-08T03:49:36.044297+00:00 [INFO] human: add a task called tui-smoke-task
2026-08-08T03:49:36.044756+00:00 [INFO] ai: Task "tui-smoke-task" added (ID 1).
...
showing 20 of 26 entries
```

To drive it manually instead of via the script, the pattern is:

```bash
export PATH="/opt/homebrew/bin:$PATH"   # if tmux isn't already on PATH
tmux new-session -d -s mytui -x 200 -y 50
tmux send-keys -t mytui "AGENT_SERVICE_URL=http://localhost:8000 ../.venv/bin/python client/main.py" Enter
sleep 2
tmux send-keys -t mytui "chat" Enter
sleep 1
tmux capture-pane -t mytui -p
```

## Run (human path)

```bash
python client/main.py   # connects to AGENT_SERVICE_URL, default http://localhost:8000
```

Drops into the same `chat`/`logs`/`session`/`exit` menu, interactively.
Useless headless/non-interactively — `Prompt.ask` blocks on a real TTY.

## Gotchas

- **Capture the tmux pane before letting the driven process exit**, not
  after. If the TUI's pane is the only pane in the only tmux session and
  you send an `exit` that lets its process count hit zero (shell included),
  the tmux **server itself** shuts down — a subsequent `capture-pane`
  fails with `no server running on /private/tmp/tmux-...`. This happened
  live while building this driver: the first version sent all `exit`s
  before capturing, and the final capture silently failed. Fix: capture
  first, exit after (see `driver.sh`'s ordering).
- The backend startup-ordering and `.env`-cwd-resolution gotchas from
  `backend/.claude/skills/run-backend/SKILL.md` apply here identically —
  the driver launches both services the same way `run-backend`'s
  `smoke.sh` does, for the same reasons.
- `view_logs`'s role labels (`human:`/`ai:`/`tool:`) only work if the
  `ROLE_STYLE` dict in `client/main.py` includes `"human"` — the
  transcript logger emits `role="human"` (not `"user"`, which is what
  `ChatHistoryResponse` uses for the *history* endpoint). A mismatch here
  isn't just a missing color: Rich raises `MarkupError: closing tag
  '[/]' has nothing to close` on the empty `[]`/`[/]` tag pair and crashes
  the whole log view. Hit this live in this session; fixed by adding
  `"human"` to `ROLE_STYLE` and guarding the markup construction so an
  unstyled role degrades to plain text instead of empty tags.

## Troubleshooting

- `tmux: command not found` — not installed; `brew install tmux`.
- Pane shows nothing after `send-keys` — increase the `sleep` before
  `capture-pane`; Groq API calls in the chat flow can take a few seconds,
  and the HITL approval round-trip (delete → interrupt → resume) took
  ~4s in this session.
- `rich.errors.MarkupError` crashing `logs` mid-view — see the
  `ROLE_STYLE` gotcha above; check `client/main.py`'s `ROLE_STYLE` dict
  covers every role value the backend actually emits (`human`, `ai`,
  `tool` from the transcript logger; `user`, `ai`, `tool` from the
  history endpoint).
