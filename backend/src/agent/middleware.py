from langchain_core.language_models import BaseChatModel
from langchain.agents.middleware import SummarizationMiddleware

from core.config import settings


def build_summarization_middleware(model: BaseChatModel) -> SummarizationMiddleware:
    return SummarizationMiddleware(
        model=model,
        keep=("messages", settings.summarization_keep_messages),
    )


# NOTE: langchain.agents.middleware.HumanInTheLoopMiddleware is a prebuilt middleware
# (no custom implementation needed). It is intentionally not attached yet because there
# are no tools requiring approval. Once a tool needs human approval, add it to the
# middleware list in agent/graph.py, e.g.:
#
#   from langchain.agents.middleware import HumanInTheLoopMiddleware
#   HumanInTheLoopMiddleware(interrupt_on={"tool_name": True})
