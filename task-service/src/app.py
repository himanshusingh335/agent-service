import logging

from fastapi import FastAPI, HTTPException
from fastapi_mcp import FastApiMCP

from core.logging import configure_logging
from db import add_task, init_db, remove_task
from models import TaskCreate, TaskDeleted, TaskOut

logger = logging.getLogger("task-mcp")


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="task-service")
    init_db()
    logger.info("task-service initialized")

    @app.post("/tasks", operation_id="add_task", response_model=TaskOut)
    def create_task(task: TaskCreate) -> TaskOut:
        row = add_task(task.title)
        return TaskOut(id=row["id"], title=row["title"], created_at=row["created_at"])

    @app.delete("/tasks/{task_id}", operation_id="remove_task", response_model=TaskDeleted)
    def delete_task(task_id: int) -> TaskDeleted:
        deleted = remove_task(task_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="task not found")
        return TaskDeleted(id=task_id, deleted=True)

    mcp = FastApiMCP(app)
    mcp.mount_http()

    return app
