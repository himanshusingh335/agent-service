import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from core.config import settings

logger = logging.getLogger("task-mcp")


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


@contextmanager
def _connect():
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def add_task(title: str) -> sqlite3.Row:
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO tasks (title, created_at) VALUES (?, ?)",
            (title, datetime.now(timezone.utc).isoformat()),
        )
        row = conn.execute(
            "SELECT id, title, created_at FROM tasks WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        logger.info("added task", extra={"task_id": row["id"], "title": row["title"]})
        return row


def remove_task(task_id: int) -> bool:
    with _connect() as conn:
        cursor = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        deleted = cursor.rowcount > 0
        logger.info("removed task", extra={"task_id": task_id, "deleted": deleted})
        return deleted
