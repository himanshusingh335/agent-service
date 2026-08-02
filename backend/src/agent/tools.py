from datetime import datetime, timezone

from langchain_core.tools import tool


@tool
def get_current_date() -> str:
    """Return the current date (UTC) in YYYY-MM-DD format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")
