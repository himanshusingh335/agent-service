import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rich.console import Console
from rich.prompt import Prompt

from api_client import AgentServiceClient

console = Console()


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
                    for chunk in client.stream(session_id, message):
                        console.print(chunk, end="")
                    console.print()
                else:
                    reply = client.invoke(session_id, message)
                    console.print(reply)
            except Exception as exc:
                console.print(f"\n[bold red]error:[/bold red] {exc}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
