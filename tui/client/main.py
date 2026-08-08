import json
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rich.console import Console
from rich.prompt import Prompt

from api_client import AgentServiceClient

console = Console()

ROLE_STYLE = {"user": "bold green", "human": "bold green", "ai": "bold magenta", "tool": "dim"}


def _handle_pending(client: AgentServiceClient, session_id: str, pending_actions: list[dict]) -> str | None:
    """Prompt for approve/reject on each pending action, resuming until the run finishes."""
    while pending_actions:
        decisions = []
        for action in pending_actions:
            console.print(
                f"\n[bold yellow]approval required[/bold yellow] — "
                f"{action['name']}({action['args']})"
            )
            if action.get("description"):
                console.print(f"[dim]{action['description']}[/dim]")
            approved = Prompt.ask(
                "[bold cyan]approve?[/bold cyan]", choices=["y", "n"], default="n"
            )
            decisions.append({"type": "approve" if approved == "y" else "reject"})

        result = client.resume(session_id, decisions)
        pending_actions = result.get("pending_actions") or []
        if not pending_actions:
            return result.get("reply")
    return None


def run_chat(client: AgentServiceClient) -> None:
    session_id = str(uuid.uuid4())
    mode = Prompt.ask(
        "[bold cyan]Response mode[/bold cyan]", choices=["stream", "invoke"], default="stream"
    )

    console.print(f"\n[bold cyan]chat[/bold cyan] — session [yellow]{session_id}[/yellow]")
    console.print(f"mode: [yellow]{mode}[/yellow] (type 'exit' to return to the menu, '/mode' to switch)\n")

    while True:
        try:
            message = console.input("[bold green]you>[/bold green] ")
        except (EOFError, KeyboardInterrupt):
            console.print()
            break

        stripped = message.strip()
        if stripped.lower() in {"exit", "quit"}:
            break
        if not stripped:
            continue
        if stripped.lower() == "/mode":
            mode = Prompt.ask(
                "[bold cyan]Response mode[/bold cyan]", choices=["stream", "invoke"], default=mode
            )
            console.print(f"switched to [yellow]{mode}[/yellow] mode\n")
            continue

        console.print("[bold magenta]agent>[/bold magenta] ", end="")
        try:
            if mode == "stream":
                pending_actions = None
                for event, chunk in client.stream(session_id, message):
                    if event == "interrupt":
                        pending_actions = json.loads(chunk)
                    else:
                        console.print(chunk, end="")
                console.print()
                if pending_actions:
                    reply = _handle_pending(client, session_id, pending_actions)
                    if reply:
                        console.print(reply)
            else:
                result = client.invoke(session_id, message)
                if result.get("pending_actions"):
                    reply = _handle_pending(client, session_id, result["pending_actions"])
                    if reply:
                        console.print(reply)
                else:
                    console.print(result.get("reply") or "")
        except Exception as exc:
            console.print(f"\n[bold red]error:[/bold red] {exc}")


def view_logs(client: AgentServiceClient) -> None:
    session_id = Prompt.ask("[bold cyan]session id[/bold cyan]").strip()
    if not session_id:
        console.print("[bold red]error:[/bold red] session id is required\n")
        return

    level = Prompt.ask(
        "[bold cyan]level[/bold cyan] (blank = all)",
        choices=["", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="",
    )
    logger_filter = Prompt.ask(
        "[bold cyan]logger[/bold cyan] (blank = all, e.g. agent.mcp, httpx, groq)",
        default="",
    ).strip()
    start_time = Prompt.ask(
        "[bold cyan]start time[/bold cyan] (ISO, e.g. 2026-08-08T00:00:00, blank = no lower bound)",
        default="",
    ).strip()
    end_time = Prompt.ask(
        "[bold cyan]end time[/bold cyan] (ISO, blank = no upper bound)", default=""
    ).strip()
    limit_raw = Prompt.ask("[bold cyan]limit[/bold cyan]", default="50").strip()
    try:
        limit = int(limit_raw)
    except ValueError:
        limit = 50

    try:
        result = client.get_logs(
            session_id,
            level=level or None,
            logger=logger_filter or None,
            start_time=start_time or None,
            end_time=end_time or None,
            limit=limit,
        )
    except Exception as exc:
        console.print(f"[bold red]error:[/bold red] {exc}\n")
        return

    logs = result.get("logs") or []
    if not logs:
        console.print("[dim]no log entries found[/dim]\n")
        return

    console.print()
    for entry in logs:
        ts = entry.get("timestamp", "")
        lvl = entry.get("level", "")
        logger_name = entry.get("logger", "")
        msg = entry.get("message", "")
        role = entry.get("role")
        style = ROLE_STYLE.get(role)
        prefix = f" [{style}]{role}:[/{style}]" if role and style else f" {role}:" if role else ""
        console.print(f"[dim]{ts} [{logger_name}][/dim] [{lvl}]{prefix} {msg}")
    console.print(f"\n[dim]showing {len(logs)} of {result.get('total', len(logs))} entries[/dim]\n")


def view_session(client: AgentServiceClient) -> None:
    session_id = Prompt.ask("[bold cyan]session id[/bold cyan]").strip()
    if not session_id:
        console.print("[bold red]error:[/bold red] session id is required\n")
        return

    try:
        result = client.get_history(session_id)
    except Exception as exc:
        console.print(f"[bold red]error:[/bold red] {exc}\n")
        return

    messages = result.get("messages") or []
    if not messages:
        console.print("[dim]no messages found for this session[/dim]\n")
        return

    console.print()
    for msg in messages:
        role = msg.get("role", "")
        style = ROLE_STYLE.get(role, "")
        console.print(f"[{style}]{role}:[/{style}] {msg.get('content', '')}")
        for tool_call in msg.get("tool_calls") or []:
            console.print(f"  [dim]-> {tool_call['name']}({tool_call['args']})[/dim]")
        if msg.get("tool_name"):
            console.print(f"  [dim](tool: {msg['tool_name']})[/dim]")
    console.print()


def main() -> None:
    base_url = os.environ.get("AGENT_SERVICE_URL", "http://localhost:8000")
    client = AgentServiceClient(base_url)

    console.print(f"[bold cyan]agent-service TUI[/bold cyan] — connected to [dim]{base_url}[/dim]\n")

    try:
        while True:
            try:
                choice = Prompt.ask(
                    "[bold cyan]What would you like to do?[/bold cyan]",
                    choices=["chat", "logs", "session", "exit"],
                    default="chat",
                )
            except (EOFError, KeyboardInterrupt):
                console.print()
                break

            if choice == "exit":
                break
            elif choice == "chat":
                run_chat(client)
            elif choice == "logs":
                view_logs(client)
            elif choice == "session":
                view_session(client)
    finally:
        client.close()


if __name__ == "__main__":
    main()
