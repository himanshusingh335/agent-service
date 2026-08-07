from langchain_core.language_models import BaseChatModel
from langchain.agents.middleware import HumanInTheLoopMiddleware, SummarizationMiddleware

from core.config import settings


def build_summarization_middleware(model: BaseChatModel) -> SummarizationMiddleware:
    return SummarizationMiddleware(
        model=model,
        keep=("messages", settings.summarization_keep_messages),
    )


def build_human_in_the_loop_middleware() -> HumanInTheLoopMiddleware:
    """Require human approval before destructive tools run.

    `remove_task` maps to the task-service `DELETE /tasks/{task_id}` MCP tool
    (operation_id `remove_task`, see task-service/src/app.py) - deletions are
    irreversible, so the agent must pause and get an explicit approve/reject
    decision before the tool actually executes.
    """
    return HumanInTheLoopMiddleware(
        interrupt_on={
            "remove_task": {
                "allowed_decisions": ["approve", "reject"],
                "description": "This will permanently delete the task. Approve?",
            }
        },
        description_prefix="Tool execution requires approval",
    )
