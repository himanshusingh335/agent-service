import json
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rich.console import Console
from rich.prompt import Prompt

from api_client import AgentServiceClient

console = Console()


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


def main() -> None:
    base_url = os.environ.get("AGENT_SERVICE_URL", "http://localhost:8000")
    session_id = str(uuid.uuid4())
    client = AgentServiceClient(base_url)

    mode = Prompt.ask(
        "[bold cyan]Response mode[/bold cyan]", choices=["stream", "invoke"], default="stream"
    )

    console.print(f"[bold cyan]agent-service TUI[/bold cyan] — session [yellow]{session_id}[/yellow]")
    console.print(
        f"connected to [dim]{base_url}[/dim] — mode: [yellow]{mode}[/yellow] "
        "(type 'exit' to quit, '/mode' to switch)\n"
    )

    try:
        while True:
            try:
                message = console.input("[bold green]you>[/bold green] ")
            except (EOFError, KeyboardInterrupt):
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
    finally:
        client.close()


if __name__ == "__main__":
    main()
